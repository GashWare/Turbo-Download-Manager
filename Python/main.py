"""
Turbo Download Manager - Master Entry Point.
Supports both modern CustomTkinter GUI and Rich CLI interfaces.
"""

from __future__ import annotations
import sys
import os

# Add current directory to path
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

# Fix Windows console UTF-8 encoding
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass


def print_detailed_help():
    """Renders a comprehensive, styled help manual and CLI reference guide."""
    try:
        from rich.console import Console
        from rich.panel import Panel
        from rich.table import Table
        from rich.text import Text

        console = Console()
        console.print()
        console.print(Panel(
            "[bold cyan]⚡ TURBO DOWNLOAD MANAGER[/bold cyan] - [dim]High-Performance Accelerated Engine[/dim]\n"
            "[bold green]Version 2.0.0[/bold green] • [yellow]Cross-Platform (Windows & Linux)[/yellow]\n"
            "[white]Equipped with both a Modern CustomTkinter GUI and an Interactive Rich Terminal CLI.[/white]",
            title="[bold white]Documentation & Reference Manual[/bold white]",
            border_style="cyan"
        ))

        console.print("\n[bold yellow]SYNOPSIS & USAGE:[/bold yellow]")
        console.print("  [cyan]python main.py[/cyan] [dim][OPTIONS][/dim]")
        console.print("  [cyan]python main.py[/cyan] [bold cyan]<COMMAND>[/bold cyan] [dim][ARGS...][/dim]")

        # Global Options Table
        opts_table = Table(title="\n[bold cyan]Global Options & Flags[/bold cyan]", border_style="dim", box=None, padding=(0, 2))
        opts_table.add_column("Flag", style="bold green", no_wrap=True)
        opts_table.add_column("Description", style="white")
        opts_table.add_row("--gui, -g", "Launch the modern CustomTkinter Graphical User Interface (Default when run with no arguments).")
        opts_table.add_row("--tray, -t, --minimized", "Launch directly into the System Tray / Notification Area in the background.")
        opts_table.add_row("--cli, -c", "Explicitly force Command-Line Interface mode.")
        opts_table.add_row("--help, -h", "Display this detailed help manual and parameter reference.")
        opts_table.add_row("--version, -v", "Display version and build information.")
        console.print(opts_table)

        # CLI Subcommands Table
        cmd_table = Table(title="\n[bold cyan]CLI Subcommands[/bold cyan]", border_style="dim", box=None, padding=(0, 2))
        cmd_table.add_column("Command", style="bold green", no_wrap=True)
        cmd_table.add_column("Syntax", style="bold cyan")
        cmd_table.add_column("Description", style="white")

        cmd_table.add_row("download", "download <URL> [options]", "Download a URL with multi-connection parallel acceleration & dynamic work-stealing.")
        cmd_table.add_row("batch", "batch <file_or_urls> [options]", "Batch queue and download URLs from a text file or comma-separated list.")
        cmd_table.add_row("monitor", "monitor", "Launch the live full-screen interactive terminal monitoring dashboard (TUI).")
        cmd_table.add_row("list", "list", "Display a formatted table of all queued, active, completed, and paused download tasks.")
        cmd_table.add_row("pause", "pause <task_id>", "Pause an ongoing active download task.")
        cmd_table.add_row("resume", "resume <task_id>", "Resume a paused or interrupted download task from where it stopped.")
        cmd_table.add_row("cancel", "cancel <task_id>", "Cancel and remove a download task from the scheduler.")
        cmd_table.add_row("status", "status <task_id>", "Inspect deep technical metadata, segment chunk breakdowns, and file paths.")
        console.print(cmd_table)

        # Parameters Table
        param_table = Table(title="\n[bold cyan]Command Parameters & Options[/bold cyan]", border_style="dim", box=None, padding=(0, 2))
        param_table.add_column("Parameter / Flag", style="bold yellow", no_wrap=True)
        param_table.add_column("Applicable To", style="dim cyan")
        param_table.add_column("Description", style="white")

        param_table.add_row("-n, --connections <1-32>", "download, batch", "Number of parallel worker threads / HTTP Range connections (default: 16).")
        param_table.add_row("-o, --output <dir>", "download, batch", "Destination directory path where downloaded files will be saved.")
        param_table.add_row("-f, --filename <name>", "download", "Custom output filename (overrides server-suggested filename).")
        param_table.add_row("-c, --checksum <hash>", "download", "Expected cryptographic hash for automatic post-download verification.")
        param_table.add_row("-a, --algo <sha256|md5>", "download", "Hash algorithm to verify against (sha256, md5, sha1, sha512; default: sha256).")
        console.print(param_table)

        # Real-world Examples
        console.print("\n[bold yellow]PRACTICAL EXAMPLES:[/bold yellow]")
        console.print("  [dim]# 1. Launch Modern Dark GUI (No args needed or use --gui):[/dim]")
        console.print("  [green]python main.py[/green]  [dim]or[/dim]  [green]python main.py --gui[/green]\n")
        console.print("  [dim]# 2. Fast single-file download with 16 parallel threads:[/dim]")
        console.print("  [green]python main.py download \"https://example.com/largefile.zip\" -n 16[/green]\n")
        console.print("  [dim]# 3. Download with custom save directory, filename, and SHA256 integrity check:[/dim]")
        console.print("  [green]python main.py download \"https://example.com/archive.iso\" -o \"C:\\Downloads\" -f \"win11.iso\" --checksum e3b0c442...[/green]\n")
        console.print("  [dim]# 4. Batch download all links listed in a text file:[/dim]")
        console.print("  [green]python main.py batch urls.txt -n 8 -o \"C:\\Downloads\"[/green]\n")
        console.print("  [dim]# 5. Monitor all downloads in a live terminal TUI:[/dim]")
        console.print("  [green]python main.py monitor[/green]\n")
        console.print("  [dim]# 6. Task Management:[/dim]")
        console.print("  [green]python main.py list[/green]")
        console.print("  [green]python main.py pause 5a3f2b1c[/green]")
        console.print("  [green]python main.py resume 5a3f2b1c[/green]")
        console.print("  [green]python main.py status 5a3f2b1c[/green]\n")

    except Exception:
        # Clean plain text fallback
        print("=" * 70)
        print("TURBO DOWNLOAD MANAGER - Command Line Reference Manual")
        print("=" * 70)
        print("\nUSAGE:")
        print("  python main.py [OPTIONS]")
        print("  python main.py <COMMAND> [ARGS...]")
        print("\nGLOBAL OPTIONS:")
        print("  --gui, -g          Launch the Graphical User Interface (Default)")
        print("  --cli, -c          Launch the Command-Line Interface")
        print("  --help, -h         Show this detailed help file and command parameters")
        print("  --version, -v      Show version information")
        print("\nCOMMANDS:")
        print("  download <URL>     Download a URL with multi-connection acceleration")
        print("                     Options: -n/--connections (1-32), -o/--output <path>,")
        print("                              -f/--filename <name>, -c/--checksum <hash>, -a/--algo <algo>")
        print("  batch <source>     Batch download URLs from file or list")
        print("                     Options: -n/--connections, -o/--output")
        print("  monitor            Open live full-screen terminal dashboard")
        print("  list               List all downloads and statuses")
        print("  pause <task_id>    Pause a running task")
        print("  resume <task_id>   Resume a paused task")
        print("  cancel <task_id>   Cancel a download task")
        print("  status <task_id>   Show detailed metadata for a task")
        print("\nEXAMPLES:")
        print("  python main.py --gui")
        print("  python main.py download \"https://example.com/file.zip\" -n 16")
        print("  python main.py batch urls.txt -n 8")
        print("  python main.py monitor")
        print("=" * 70)


def main():
    if len(sys.argv) == 1:
        # Launch modern GUI by default when run with no arguments
        from gui.gui_app import main as run_gui
        run_gui()
    elif sys.argv[1] in ("--tray", "-t", "--minimized", "--background"):
        from gui.gui_app import main as run_gui
        initial_url = sys.argv[2] if len(sys.argv) > 2 else ""
        run_gui(initial_url=initial_url, start_in_tray=True)
    elif sys.argv[1] in ("--gui", "-g"):
        from gui.gui_app import main as run_gui
        initial_url = sys.argv[2] if len(sys.argv) > 2 else ""
        run_gui(initial_url=initial_url)
    elif len(sys.argv) == 2 and sys.argv[1] in ("--help", "-h", "help"):
        print_detailed_help()
    elif len(sys.argv) == 2 and sys.argv[1] in ("--version", "-v"):
        print("Turbo Download Manager v2.0.0 (High-Performance Engine)")
    elif len(sys.argv) == 2 and sys.argv[1] == "--register-protocols":
        from core.protocol_handler import register_all_associations
        m_ok, t_ok = register_all_associations()
        print(f"Magnet registration: {'OK' if m_ok else 'Failed'}, Torrent registration: {'OK' if t_ok else 'Failed'}")
    elif len(sys.argv) == 2 and sys.argv[1] == "--unregister-protocols":
        from core.protocol_handler import unregister_all_associations
        m_ok, t_ok = unregister_all_associations()
        print(f"Magnet unregistration: {'OK' if m_ok else 'Failed'}, Torrent unregistration: {'OK' if t_ok else 'Failed'}")
    elif len(sys.argv) >= 2 and sys.argv[1] in ("--cli", "-c"):
        # Remove --cli / -c flag and pass remainder to CLI parser
        sys.argv.pop(1)
        if not sys.argv[1:]:
            print_detailed_help()
        else:
            from cli.cli_app import main as run_cli
            run_cli()
    else:
        first_arg = sys.argv[1]
        target_url = first_arg

        # Handle turbodm:// custom protocol (e.g., turbodm://add?url=https%3A%2F%2F...)
        if first_arg.startswith("turbodm://"):
            import urllib.parse
            raw = first_arg[len("turbodm://"):]
            if raw.startswith("add?") or raw.startswith("download?"):
                qs = urllib.parse.parse_qs(raw.split("?", 1)[1])
                target_url = qs.get("url", [""])[0]
            elif raw.startswith("http://") or raw.startswith("https://") or raw.startswith("magnet:"):
                target_url = raw
            else:
                target_url = urllib.parse.unquote(raw)

        # Check if launched with a URL/protocol and forward to running GUI instance if alive
        if target_url.startswith(("http://", "https://", "magnet:")) or target_url.lower().endswith(".torrent") or (os.path.isfile(target_url) and target_url.lower().endswith(".torrent")):
            from core.api_server import send_url_to_running_instance
            if send_url_to_running_instance(target_url):
                print(f"[+] Download sent to active Turbo Download Manager: {target_url}")
                return

        # Check if launched with a magnet link or .torrent file or turbodm://
        if first_arg.startswith("turbodm://") or first_arg.startswith("magnet:") or first_arg.lower().endswith(".torrent") or (os.path.isfile(first_arg) and first_arg.lower().endswith(".torrent")):
            from gui.gui_app import main as run_gui
            run_gui(initial_url=target_url)
        elif first_arg in ("download", "batch", "monitor", "list", "pause", "resume", "cancel", "status"):
            from cli.cli_app import main as run_cli
            run_cli()
        elif first_arg.startswith(("http://", "https://")):
            # Convenience shortcut: `python main.py https://...` -> `python main.py download https://...`
            sys.argv.insert(1, "download")
            from cli.cli_app import main as run_cli
            run_cli()
        elif first_arg in ("--help", "-h"):
            print_detailed_help()
        else:
            from cli.cli_app import main as run_cli
            run_cli()


if __name__ == "__main__":
    main()

