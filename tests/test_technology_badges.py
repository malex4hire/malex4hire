"""Technology badges are optional card metadata and render below the headline."""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from render_readme import card_markdown


def test_declared_technology_badges_render_below_the_headline():
    card = {
        "line": "Workflow demonstration",
        "proves": "Evidence remains below the stack.",
        "bindings": [{"kind": "artifact", "value": "README.md", "path": "README.md"}],
        "technologies": [
            {"name": "Go", "logo": "go", "color": "00ADD8"},
            {"name": "Java", "logo": "openjdk", "color": "ED8B00"},
        ],
    }
    page = card_markdown("demo", card)
    assert "![Go](https://img.shields.io/badge/Go-00ADD8?logo=go&logoColor=white)" in page
    assert "![Java](https://img.shields.io/badge/Java-ED8B00?logo=openjdk&logoColor=white)" in page
    assert page.index("Workflow demonstration") < page.index("![Go]") < page.index(card["proves"])
    assert "| artifact | `README.md` |" in page


def test_omitting_technology_metadata_preserves_the_card_format():
    card = {
        "line": "Workflow demonstration",
        "proves": "Evidence.",
        "bindings": [{"kind": "artifact", "value": "README.md", "path": "README.md"}],
    }
    assert card_markdown("demo", card) == card_markdown("demo", {**card, "technologies": []})
    assert "shields.io" not in card_markdown("demo", card)


def test_existing_repository_badge_urls_are_preserved():
    url = "https://img.shields.io/badge/Google_ADK-2.9.2%2B-4285F4?logo=googlecloud&logoColor=white"
    card = {
        "proves": "Evidence.",
        "bindings": [{"kind": "artifact", "value": "README.md", "path": "README.md"}],
        "technologies": [{"name": "Google ADK", "url": url}],
    }
    assert f"![Google ADK]({url})" in card_markdown("demo", card)
