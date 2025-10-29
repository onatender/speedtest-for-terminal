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


def run_speedtest(secure: bool, live: bool) -> Dict[str, Any]:
	# Import inside function so the script starts fast and import errors are clear
	import speedtest  # type: ignore

	st = speedtest.Speedtest(secure=secure)

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
		run_with_spinner(lambda: st.download(), "İndirme ölçülüyor")
		print(f"{Fore.GREEN}✓{Style.RESET_ALL} İndirme: {Fore.GREEN}{format_mbps(st.results.download)}{Style.RESET_ALL}", flush=True)
		run_with_spinner(lambda: st.upload(pre_allocate=False), "Yükleme ölçülüyor")
		print(f"{Fore.GREEN}✓{Style.RESET_ALL} Yükleme: {Fore.GREEN}{format_mbps(st.results.upload)}{Style.RESET_ALL}", flush=True)
	else:
		st.get_servers()
		st.get_best_server()
		st.download()
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
	parser.add_argument(
		"--no-secure",
		action="store_true",
		help="Disable HTTPS for test endpoints (default: secure on)",
	)
	args = parser.parse_args()

	try:
		# Initialize color output on Windows terminals
		colorama_init()
		results = run_speedtest(secure=not args.no_secure, live=not args.no_live and not args.json)
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


