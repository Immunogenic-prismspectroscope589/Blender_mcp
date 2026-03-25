import re
import sys
from collections import defaultdict
from pathlib import Path


def main():
    if len(sys.argv) < 2:
        print("Usage: python remove_unused_ignores.py <mypy_output.txt>")
        sys.exit(1)

    mypy_output = Path(sys.argv[1]).read_text(encoding="utf-8")

    # Map file -> lines to modify
    # Format: "path/to/file.py:123: error: Unused "type: ignore" comment"
    # or "[unused-ignore]"

    # Regex for file:line: error:
    header_pattern = re.compile(r"^(.+?):(\d+): error:(.*)")

    corrections = defaultdict(set)
    lines = mypy_output.splitlines()

    for i, line in enumerate(lines):
        match = header_pattern.match(line)
        if match:
            filepath = match.group(1).strip()
            lineno = int(match.group(2))
            msg = match.group(3).strip()

            # Check if this line OR next few lines contain "Unused" or "[unused-ignore]"
            is_unused = 'Unused "type: ignore"' in msg or "[unused-ignore]" in msg

            if not is_unused and i + 1 < len(lines):
                next_line = lines[i + 1]
                if 'Unused "type: ignore"' in next_line or "[unused-ignore]" in next_line:
                    is_unused = True

            if not is_unused and i + 2 < len(lines):
                next_line = lines[i + 2]
                if "[unused-ignore]" in next_line:
                    is_unused = True

            if is_unused:
                corrections[filepath].add(lineno)

    print(f"Found {sum(len(v) for v in corrections.values())} unused ignores to remove.")

    for filepath, ignore_lines in corrections.items():
        path = Path(filepath)
        if not path.exists():
            print(f"File not found: {filepath}")
            continue

        content = path.read_text(encoding="utf-8").splitlines()
        modified = False
        new_content = []  # Initialize new_content for each file

        # Sort lines descending to keep indices valid if we were deleting lines,
        # but here we are modifying lines, so specific order isn't strictly necessary
        # but safe to process.
        # Actually line numbers are 1-based.

        for i, line in enumerate(content):
            current_lineno = i + 1
            if current_lineno in ignore_lines:
                # Remove type: ignore
                # Handles:
                # 1. code  # type: ignore
                # 2. code  # type: ignore[code]
                # 3. code  # type: ignore [code]

                # We want to remove the comment, but keep the code.
                # Regex to find the comment at the end of the line

                # Check if the line ends with the ignore
                # A robust regex to remove '  # type: ignore...'
                # We should be careful not to remove valid code.

                # Pattern: space + # + space* + type: ignore... $
                replacement = re.sub(r"\s*#\s*type:\s*ignore.*$", "", line)
                if replacement != line:
                    new_content.append(replacement)
                    modified = True
                else:
                    new_content.append(line)
            else:
                new_content.append(line)

        if modified:
            print(f"Modifying {filepath}")
            path.write_text("\n".join(new_content) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
