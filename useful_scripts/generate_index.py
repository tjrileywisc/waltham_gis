"""Render published/index.html from the html files present in published/."""

from pathlib import Path

from jinja2 import Environment, FileSystemLoader

REPO_ROOT = Path(__file__).resolve().parent.parent
PUBLISHED_DIR = REPO_ROOT / "published"
TEMPLATE_DIR = Path(__file__).resolve().parent / "templates"


def title_from_filename(path: Path) -> str:
    return path.stem.replace("_", " ").replace("-", " ").title()


def main() -> None:
    pages = [
        {"href": path.name, "title": title_from_filename(path)}
        for path in sorted(PUBLISHED_DIR.glob("*.html"))
        if path.name != "index.html"
    ]

    env = Environment(loader=FileSystemLoader(TEMPLATE_DIR))
    template = env.get_template("index.html.j2")
    (PUBLISHED_DIR / "index.html").write_text(template.render(pages=pages), encoding="utf-8")


if __name__ == "__main__":
    main()
