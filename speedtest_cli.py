import argparse
import sys
import threading
import time
from typing import Any, Dict, Callable

try:
	from colorama import init as colorama_init, Fore, Style
except Exception:  # fallback if not installed (JSON mode or import error)
	class _Dummy:
		RESET_ALL = ""
		BRIGHT = ""
		DIM = ""
		CYAN = ""
		GREEN = ""
		YELLOW = ""
		RED = ""

	Style = _Dummy()
	Fore = _Dummy()
	def colorama_init():  # type: ignore
		return None


def format_mbps(bits_per_second: float) -> str:
	if bits_per_second is None:
		return "-"
	return f"{bits_per_second / 1_000_000:.2f} Mbps"


def run_with_spinner(func: Callable[[], Any], label: str) -> Any:
	spinner_chars = ["⠋", "⠙", "⠸", "⠴", "⠦", "⠇"]
	result_container: Dict[str, Any] = {}
	exc_container: Dict[str, BaseException] = {}
	finished = threading.Event()

	def _target() -> None:
		try:
			result_container["value"] = func()
		except BaseException as e:  # surface interrupts and errors
			exc_container["exc"] = e
		finally:
			finished.set()

	thread = threading.Thread(target=_target, daemon=True)
	thread.start()
	idx = 0
	start_ts = time.time()
	while not finished.is_set():
		ch = spinner_chars[idx % len(spinner_chars)]
		elapsed = time.time() - start_ts
		print(
			f"{Style.DIM}{Fore.CYAN}{ch} {label}{Style.RESET_ALL} "
			f"{Style.DIM}({elapsed:.1f}s){Style.RESET_ALL}    ",
			end="\r",
			flush=True,
		)
		time.sleep(0.1)
		idx += 1
	# clear line
	print(" " * 80, end="\r")

	if "exc" in exc_container:
		raise exc_container["exc"]
	return result_container.get("value")


def _timed_transfer_download(server: Dict[str, Any], duration_s: int, threads: int = 4) -> float:
	import requests  # type: ignore

	base_url = server.get("url", "")
	# Expect something like http://host:port/speedtest/upload.php -> make .../speedtest
	if base_url.endswith("upload.php"):
		base_url = base_url.rsplit("/", 1)[0]
	sizes = [350, 500, 750, 1000, 1500, 2000, 2500, 3000, 3500, 4000]
	stop_at = time.time() + duration_s
	bytes_total = 0
	bytes_lock = threading.Lock()

	def worker(idx: int) -> None:
		n = idx % len(sizes)
		local_bytes = 0
		while time.time() < stop_at:
			size = sizes[n]
			dl_url = f"{base_url}/random{size}x{size}.jpg"
			try:
				with requests.get(dl_url, stream=True, timeout=(3, 3)) as resp:
					resp.raise_for_status()
					for chunk in resp.iter_content(chunk_size=65536):
						if not chunk:
							continue
						local_bytes += len(chunk)
						if time.time() >= stop_at:
							break
			except Exception:
				pass
			n = (n + 1) % len(sizes)
		with bytes_lock:
			nonlocal bytes_total
			bytes_total += local_bytes

	threads_list = [threading.Thread(target=worker, args=(i,), daemon=True) for i in range(max(1, threads))]
	for t in threads_list:
		t.start()
	for t in threads_list:
		t.join()
	# return bits per second
	return (bytes_total * 8) / max(0.001, duration_s)


def _timed_transfer_upload(server: Dict[str, Any], duration_s: int, threads: int = 4) -> float:
	import requests  # type: ignore
	import os

	base_url = server.get("url", "")
	if not base_url.endswith("upload.php"):
		if base_url.endswith("/"):
			base_url = base_url + "upload.php"
		else:
			base_url = base_url + "/upload.php"

	payload = os.urandom(1024 * 256)  # 256 KB chunks
	stop_at = time.time() + duration_s
	bytes_total = 0
	bytes_lock = threading.Lock()

	def worker() -> None:
		local_bytes = 0
		while time.time() < stop_at:
			try:
				# send as multipart to mimic speedtest servers
				files = {"file": ("payload.bin", payload, "application/octet-stream")}
				resp = requests.post(base_url, files=files, timeout=(3, 3))
				resp.raise_for_status()
				local_bytes += len(payload)
			except Exception:
				pass
		with bytes_lock:
			nonlocal bytes_total
			bytes_total += local_bytes

	threads_list = [threading.Thread(target=worker, daemon=True) for _ in range(max(1, threads))]
	for t in threads_list:
		t.start()
	for t in threads_list:
		t.join()
	return (bytes_total * 8) / max(0.001, duration_s)


def run_speedtest(secure: bool, live: bool, do_download: bool, do_upload: bool, timeout_s: int | None) -> Dict[str, Any]:
	# Import inside function so the script starts fast and import errors are clear
	import speedtest  # type: ignore

	# timeout controls HTTP timeouts, not true test duration
	st = speedtest.Speedtest(secure=secure, timeout=timeout_s or 10)

	if live:
		run_with_spinner(lambda: st.get_servers(), "Sunucular yükleniyor")
		best = run_with_spinner(lambda: st.get_best_server(), "En iyi sunucu bulunuyor")
		if isinstance(best, dict):
			lat = best.get("latency")
			print(
				f"{Fore.CYAN}Sunucu{Style.RESET_ALL}: {best.get('sponsor', '-')}, {best.get('name', '-')}, {best.get('country', '-')} "
				f"| {Fore.CYAN}Gecikme{Style.RESET_ALL}: "
				+ (f"{Fore.YELLOW}{lat:.2f} ms{Style.RESET_ALL}" if isinstance(lat, (int, float)) else "-"),
				flush=True,
			)
		# download/upload (bloklayıcı), spinner ile göster
		if timeout_s and timeout_s > 0:
			# time-bounded custom measurement
			if do_download:
				bps_down = run_with_spinner(lambda: _timed_transfer_download(best if isinstance(best, dict) else st.best, timeout_s), "İndirme ölçülüyor")
				st.results.download = float(bps_down)
				print(f"{Fore.GREEN}✓{Style.RESET_ALL} İndirme: {Fore.GREEN}{format_mbps(st.results.download)}{Style.RESET_ALL}", flush=True)
			if do_upload:
				bps_up = run_with_spinner(lambda: _timed_transfer_upload(best if isinstance(best, dict) else st.best, timeout_s), "Yükleme ölçülüyor")
				st.results.upload = float(bps_up)
				print(f"{Fore.GREEN}✓{Style.RESET_ALL} Yükleme: {Fore.GREEN}{format_mbps(st.results.upload)}{Style.RESET_ALL}", flush=True)
		else:
			if do_download:
				run_with_spinner(lambda: st.download(), "İndirme ölçülüyor")
				print(f"{Fore.GREEN}✓{Style.RESET_ALL} İndirme: {Fore.GREEN}{format_mbps(st.results.download)}{Style.RESET_ALL}", flush=True)
			if do_upload:
				run_with_spinner(lambda: st.upload(pre_allocate=False), "Yükleme ölçülüyor")
				print(f"{Fore.GREEN}✓{Style.RESET_ALL} Yükleme: {Fore.GREEN}{format_mbps(st.results.upload)}{Style.RESET_ALL}", flush=True)
	else:
		st.get_servers()
		st.get_best_server()
		if timeout_s and timeout_s > 0:
			# time-bounded custom measurement
			best = st.best
			if do_download:
				st.results.download = float(_timed_transfer_download(best, timeout_s))
			if do_upload:
				st.results.upload = float(_timed_transfer_upload(best, timeout_s))
		else:
			if do_download:
				st.download()
			if do_upload:
				st.upload(pre_allocate=False)

	results = st.results.dict()
	return results


def main() -> int:
	parser = argparse.ArgumentParser(
		description="Terminal speedtest. Builds to single-file exe with PyInstaller."
	)
	parser.add_argument(
		"--json",
		action="store_true",
		help="Output raw JSON results"
	)
	parser.add_argument(
		"--no-live",
		action="store_true",
		help="Disable live progress output",
	)
	# Provide -help alias for convenience
	parser.add_argument(
		"-help",
		action="help",
		help="Show this help message and exit",
	)
	parser.add_argument(
		"-t",
		"--time",
		type=int,
		default=1,
		help="Duration in seconds for the measurement (default: 1). Uses timed transfers.",
	)
	parser.add_argument(
		"--upload-only",
		action="store_true",
		help="Run only upload test",
	)
	parser.add_argument(
		"--download-only",
		action="store_true",
		help="Run only download test",
	)
	parser.add_argument(
		"--no-secure",
		action="store_true",
		help="Disable HTTPS for test endpoints (default: secure on)",
	)
	args = parser.parse_args()

	try:
		# Initialize color output on Windows terminals
		colorama_init()
		if args.upload_only and args.download_only:
			print("Error: cannot use both --upload-only and --download-only", file=sys.stderr)
			return 2
		do_download = not args.upload_only
		do_upload = not args.download_only
		results = run_speedtest(
			secure=not args.no_secure,
			live=not args.no_live and not args.json,
			do_download=do_download,
			do_upload=do_upload,
			timeout_s=args.time,
		)
		if args.json:
			import json
			print(json.dumps(results, ensure_ascii=False))
			return 0

		client = results.get("client", {}) or {}
		download_bps = results.get("download")
		upload_bps = results.get("upload")
		ping_ms = results.get("ping")
		server = results.get("server", {}) or {}

		lines = [
			f"{Style.BRIGHT}Speedtest Results{Style.RESET_ALL}",
			f"{Style.DIM}=================={Style.RESET_ALL}",
			f"{Fore.CYAN}ISP       {Style.RESET_ALL}: {client.get('isp', '-')}",
			f"{Fore.CYAN}IP        {Style.RESET_ALL}: {client.get('ip', '-')}",
			f"{Fore.CYAN}Location  {Style.RESET_ALL}: {client.get('country', '-')}",
			"",
			f"{Fore.CYAN}Server    {Style.RESET_ALL}: {server.get('sponsor', '-')}, {server.get('name', '-')}, {server.get('country', '-')}",
			(
				f"{Fore.CYAN}Latency   {Style.RESET_ALL}: {Fore.YELLOW}{ping_ms:.2f} ms{Style.RESET_ALL}"
				if isinstance(ping_ms, (int, float))
				else f"{Fore.CYAN}Latency   {Style.RESET_ALL}: -"
			),
			f"{Fore.CYAN}Download  {Style.RESET_ALL}: {Fore.GREEN}{format_mbps(download_bps)}{Style.RESET_ALL}",
			f"{Fore.CYAN}Upload    {Style.RESET_ALL}: {Fore.GREEN}{format_mbps(upload_bps)}{Style.RESET_ALL}",
		]
		print("\n".join(lines))
		return 0
	except KeyboardInterrupt:
		print("Aborted by user.")
		return 130
	except Exception as exc:
		print(f"Error: {exc}", file=sys.stderr)
		return 1


if __name__ == "__main__":
	sys.exit(main())


