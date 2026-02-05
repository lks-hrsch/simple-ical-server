import argparse
import re
import subprocess
import sys
import tomllib
from pathlib import Path

import semver


def run_command(command, check=True, dry_run=False):
    if dry_run and any(x in command for x in ["push", "tag", "commit"]):
        print(f"[DRY-RUN] Would run: {command}")
        return ""

    result = subprocess.run(command, shell=True, capture_output=True, text=True)
    if check and result.returncode != 0:
        print(f"Error running command: {command}")
        print(result.stderr)
        sys.exit(1)
    return result.stdout.strip()


def get_current_version():
    with open("pyproject.toml", "rb") as f:
        data = tomllib.load(f)
    return data["project"]["version"]


def get_last_tag():
    # Get the most recent tag
    tags = run_command("git tag -l 'v*' --sort=-v:refname", check=False).splitlines()
    return tags[0] if tags else None


def determine_bump_type(last_tag):
    if not last_tag:
        return "patch"  # Initial release

    commits = run_command(f"git log {last_tag}..HEAD --oneline")
    if not commits:
        print("No new commits since last tag.")
        sys.exit(0)

    is_major = "BREAKING CHANGE" in commits or "!:" in commits
    is_minor = re.search(r"\bfeat:", commits) or re.search(r"\bfeature:", commits)

    if is_major:
        return "major"
    if is_minor:
        return "minor"
    return "patch"


def update_version(new_version):
    # We'll use a simple string replacement to avoid losing comments in pyproject.toml
    content = Path("pyproject.toml").read_text()
    new_content = re.sub(r'version = "[^"]+"', f'version = "{new_version}"', content, count=1)
    Path("pyproject.toml").write_text(new_content)


def main():
    parser = argparse.ArgumentParser(description="Semver release script")
    parser.add_argument("--dry-run", action="store_true", help="Don't actually commit or push")
    args = parser.parse_args()

    # Ensure we are on main branch
    branch = run_command("git rev-parse --abbrev-ref HEAD")
    if branch != "main":
        print(f"Error: Must be on main branch to release. (Currently on {branch})")
        sys.exit(1)

    # Check for uncommitted changes (only if not dry run)
    if not args.dry_run:
        status = run_command("git status --porcelain")
        if status:
            print("Error: Uncommitted changes found. Please commit or stash them first.")
            sys.exit(1)

    current_version = get_current_version()
    last_tag = get_last_tag()
    bump_type = determine_bump_type(last_tag)

    ver = semver.Version.parse(current_version)
    if bump_type == "major":
        new_version = str(ver.bump_major())
    elif bump_type == "minor":
        new_version = str(ver.bump_minor())
    else:
        new_version = str(ver.bump_patch())

    print(f"Current version: {current_version}")
    print(f"Last tag: {last_tag}")
    print(f"Bump type: {bump_type}")
    print(f"New version: {new_version}")

    if args.dry_run:
        print("[DRY-RUN] Finished analysis. No changes made.")
        return

    # Ask for confirmation
    confirm = input(f"Release v{new_version}? (y/n): ")
    if confirm.lower() != "y":
        print("Release cancelled.")
        sys.exit(0)

    # 1. Update pyproject.toml
    print(f"Updating pyproject.toml to {new_version}...")
    update_version(new_version)
    run_command("uv lock")

    # 2. Commit and Push version change
    print("Committing and pushing version bump...")
    run_command("git add pyproject.toml uv.lock")
    run_command(f'git commit -m "chore: bump version to v{new_version}"')
    run_command("git push origin main", dry_run=args.dry_run)

    # 3. Create and Push Tag
    print(f"Creating and pushing tag v{new_version}...")
    run_command(f"git tag -a v{new_version} -m 'Release v{new_version}'", dry_run=args.dry_run)
    run_command(f"git push origin v{new_version}", dry_run=args.dry_run)

    print(f"Successfully released v{new_version}")


if __name__ == "__main__":
    main()
