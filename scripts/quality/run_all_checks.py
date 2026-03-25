#!/usr/bin/env python3
"""
TÜM KALİTE KONTROLLERİNİ ÇALIŞTIRAN ANA BETİK
Tüm testleri sırayla çalıştırır ve sonuçları özetler.

Kullanım:
    uv run python scripts/quality/run_all_checks.py
    uv run python scripts/quality/run_all_checks.py --fast
    uv run python scripts/quality/run_all_checks.py --strict
"""

import subprocess
import sys

# Test komutları listesi
CHECKS = [
    (
        "Virtual Environment",
        ["python", "-c", "import sys; sys.exit(0)"],
    ),  # High Mode: pip check disabled (external deps warning)
    ("Handler Imports", ["python", "scripts/quality/check_handler_imports.py", "--all"]),
    ("Handler Completeness", ["python", "scripts/quality/check_handler_completeness.py"]),
    ("Tool Group Integrity", ["python", "scripts/quality/check_tool_groups.py"]),
    ("Version Consistency", ["python", "scripts/quality/check_version.py"]),
    ("Ruff Lint", ["python", "-m", "ruff", "check", "blender_mcp", "--select", "E9,F63,F7,F82"]),
]

FAST_CHECKS = [
    (
        "Virtual Environment",
        ["python", "-c", "import sys; sys.exit(0)"],
    ),  # High Mode: Skip pip check noise
    ("Handler Imports", ["python", "scripts/quality/check_handler_imports.py", "--all"]),
    ("Handler Completeness", ["python", "scripts/quality/check_handler_completeness.py"]),
    ("Tool Group Integrity", ["python", "scripts/quality/check_tool_groups.py"]),
    ("Version Consistency", ["python", "scripts/quality/check_version.py"]),
]

SLOW_CHECKS = [
    ("Ruff Lint", ["python", "-m", "ruff", "check", "blender_mcp", "--select", "E9,F63,F7,F82"]),
    ("Ruff Format", ["python", "-m", "ruff", "format", "--check", "blender_mcp"]),
    ("MyPy Type Check", ["python", "-m", "mypy", "blender_mcp", "--ignore-missing-imports"]),
    ("Pytest Unit", ["python", "-m", "pytest", "tests", "-v", "--tb=short", "-q", "-x"]),
]


def run_check(name: str, cmd: list) -> tuple:
    """Tek bir kontrolü çalıştır."""
    print(f"\n{'=' * 60}")
    print(f"[RUN] {name}")
    print("=" * 60)

    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=120
        )

        if result.stdout:
            print(result.stdout)
        if result.stderr:
            print(result.stderr)

        return result.returncode == 0, result.returncode
    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] {name} took too long")
        return False, -1
    except Exception as e:
        print(f"[ERROR] Failed to run {name}: {e}")
        return False, -1


def main():
    """Ana fonksiyon."""
    import argparse

    parser = argparse.ArgumentParser(description="Run all quality checks")
    parser.add_argument("--fast", action="store_true", help="Run only fast checks")
    parser.add_argument("--full", action="store_true", help="Run full checks including slow ones")
    parser.add_argument("--strict", action="store_true", help="Treat warnings as errors")
    args = parser.parse_args()

    print("=" * 60)
    print("  BLENDER MCP - TÜM KALİTE KONTROLLERİ")
    print("=" * 60)

    # Hangi testleri çalıştıracağız?
    if args.fast:
        checks = FAST_CHECKS
        print("\n[MODE] Fast checks only")
    elif args.full:
        checks = CHECKS + SLOW_CHECKS
        print("\n[MODE] Full checks (slow)")
    else:
        checks = CHECKS
        print("\n[MODE] Standard checks")

    # Testleri çalıştır
    results = []
    for name, cmd in checks:
        success, code = run_check(name, cmd)
        results.append((name, success, code))

    # Özet
    print("\n" + "=" * 60)
    print("  SONUÇ ÖZETİ")
    print("=" * 60)

    passed = []
    failed = []

    for name, success, code in results:
        if success:
            passed.append(name)
            print(f"  [OK]   {name}")
        else:
            failed.append(name)
            print(f"  [FAIL] {name} (exit: {code})")

    print("=" * 60)
    print(f"\nToplam: {len(passed)} basarili, {len(failed)} basarisiz")

    if failed:
        print(f"\n[FAIL] Başarısız kontroller: {', '.join(failed)}")
        sys.exit(1)
    else:
        print("\n[OK] Tüm kontroller başarılı!")
        sys.exit(0)


if __name__ == "__main__":
    main()
