"""
Presentation CLI — the demo front-end.

A polished terminal interface over the existing pipeline. This changes NO
logic: it calls exactly the same functions as main.py / embed_and_search.py /
ask.py, and only presents the output more clearly.

Usage:
    python demo.py                # interactive menu (use this on Thursday)
    python demo.py --pipeline     # jump straight to the ETL pipeline
    python demo.py --search       # jump straight to semantic search
    python demo.py --rag          # jump straight to RAG
"""

import sys
import time

from rich.align import Align
from rich.console import Console, Group
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table
from rich.text import Text

from src import export, extract, load, upload
from src.config import validate_config
from src.embed import get_model
from src.rag import ask as rag_ask
from src.search import keyword_search, semantic_search

console = Console()

# Colour scheme — consistent throughout
C_ACCENT = "bright_cyan"
C_OK = "bright_green"
C_WARN = "yellow"
C_DIM = "grey58"
C_BAD = "bright_red"


# ----------------------------------------------------------------- CHROME

def banner() -> None:
    """The title card."""
    console.clear()

    title = Text()
    title.append("STOCK MARKET ETL PIPELINE\n", style=f"bold {C_ACCENT}")
    title.append("with Semantic Search & RAG", style=C_DIM)

    flow = Text()
    flow.append("Finnhub API", style=C_ACCENT)
    flow.append("  →  ", style=C_DIM)
    flow.append("Python", style=C_ACCENT)
    flow.append("  →  ", style=C_DIM)
    flow.append("MongoDB (EC2)", style=C_ACCENT)
    flow.append("  →  ", style=C_DIM)
    flow.append("JSON", style=C_ACCENT)
    flow.append("  →  ", style=C_DIM)
    flow.append("AWS S3", style=C_ACCENT)

    console.print()
    console.print(
        Panel(
            Align.center(Group(Align.center(title), Text(), Align.center(flow))),
            border_style=C_ACCENT,
            padding=(1, 4),
        )
    )
    console.print()


def stage(number: int, total: int, name: str, detail: str = "") -> None:
    """A stage header, e.g.  [1/4] EXTRACT."""
    text = Text()
    text.append(f"  {number}/{total}  ", style=f"bold {C_ACCENT}")
    text.append(name, style="bold white")
    if detail:
        text.append(f"   {detail}", style=C_DIM)

    console.print()
    console.print(text)
    console.print(Rule(style=C_DIM))


# --------------------------------------------------------------- PIPELINE

def demo_pipeline() -> None:
    """The four-stage ETL pipeline, presented cleanly."""
    banner()
    console.print(Rule("[bold]ETL PIPELINE[/bold]", style=C_ACCENT))

    # --- 1. EXTRACT ---
    stage(1, 4, "EXTRACT", "Finnhub API → Python")

    with console.status("[cyan]Calling Finnhub…", spinner="dots"):
        companies = extract.extract_all()

    if not companies:
        console.print(f"[{C_BAD}]  Extraction failed — aborting.[/]")
        return

    table = Table(box=None, padding=(0, 2), header_style=f"bold {C_DIM}")
    table.add_column("Ticker", style=f"bold {C_ACCENT}")
    table.add_column("Company")
    table.add_column("Industry", style=C_DIM)
    table.add_column("Price", justify="right", style=C_OK)
    table.add_column("Change", justify="right")

    for c in companies:
        pct = c.get("percent_change")
        if pct is None:
            change = Text("—", style=C_DIM)
        elif pct >= 0:
            change = Text(f"▲ {pct:.2f}%", style=C_OK)
        else:
            change = Text(f"▼ {abs(pct):.2f}%", style=C_BAD)

        table.add_row(
            c["ticker"],
            c["name"],
            c.get("industry") or "—",
            f"${c.get('current_price')}",
            change,
        )

    console.print(table)
    console.print(f"  [{C_OK}]✓[/] Extracted {len(companies)} companies")

    # --- 2. LOAD ---
    stage(2, 4, "LOAD", "Python → MongoDB on EC2")

    with console.status("[cyan]Writing to MongoDB…", spinner="dots"):
        load.upsert_companies(companies)
        count = load.count_documents()

    console.print(f"  [{C_OK}]✓[/] MongoDB holds [bold]{count}[/] companies")
    console.print(
        f"  [{C_DIM}]upsert keyed on ticker — re-running refreshes, never duplicates[/]"
    )

    # --- 3. EXPORT ---
    stage(3, 4, "EXPORT", "MongoDB → JSON")

    with console.status("[cyan]Serializing…", spinner="dots"):
        stored = load.find_all()
        path = export.export_to_file(stored)
        intact = export.verify_export(path, len(stored))

    console.print(f"  [{C_OK}]✓[/] Exported → [bold]{path}[/]")
    if intact:
        console.print(
            f"  [{C_OK}]✓[/] Integrity check passed — "
            f"{len(stored)} documents round-tripped intact"
        )

    # --- 4. UPLOAD ---
    stage(4, 4, "UPLOAD", "JSON → AWS S3")

    with console.status("[cyan]Uploading to S3…", spinner="dots"):
        key = upload.upload_file(path)

    if key:
        console.print(f"  [{C_OK}]✓[/] Uploaded → [bold]s3://…/{key}[/]")

    console.print()
    console.print(
        Panel(
            Align.center(Text("PIPELINE COMPLETE", style=f"bold {C_OK}")),
            border_style=C_OK,
        )
    )


# ---------------------------------------------------------- SEMANTIC SEARCH

def show_search(query: str) -> None:
    """Keyword vs semantic, side by side — the money shot."""
    console.print()
    console.print(
        Panel(
            Text(f'"{query}"', style=f"bold {C_ACCENT}", justify="center"),
            title="[bold]QUERY[/bold]",
            border_style=C_ACCENT,
        )
    )

    # --- keyword ---
    console.print()
    console.print("  [bold]KEYWORD SEARCH[/bold]  [grey58]matches letters[/]")

    kw = keyword_search(query)

    if kw:
        for r in kw:
            console.print(f"    [{C_OK}]•[/] {r['ticker']}  {r['name']}")
    else:
        console.print(
            f"    [{C_BAD}]✗  No results[/] "
            f"[{C_DIM}]— no company contains that exact text[/]"
        )

    # --- semantic ---
    console.print()
    console.print("  [bold]SEMANTIC SEARCH[/bold]  [grey58]matches meaning[/]")

    results = semantic_search(query, top_k=3)

    table = Table(box=None, padding=(0, 2), show_header=False)
    table.add_column(style=f"bold {C_ACCENT}")   # ticker
    table.add_column()                            # name
    table.add_column(justify="right")             # score
    table.add_column()                            # bar

    for r in results:
        score = r["score"]
        # Strong match vs noise — the gap is the evidence
        colour = C_OK if score > 0.5 else C_WARN if score > 0.4 else C_DIM
        bar = "█" * max(1, int(score * 24))

        table.add_row(
            r["ticker"],
            r["name"],
            f"[{colour}]{score:.3f}[/]",
            f"[{colour}]{bar}[/]",
        )

    console.print(table)
    console.print()


def demo_search() -> None:
    banner()
    console.print(Rule("[bold]SEMANTIC SEARCH[/bold]", style=C_ACCENT))

    console.print()
    console.print(
        Panel(
            "[bold]Keyword search matches letters. Semantic search matches meaning.[/bold]\n\n"
            "[grey58]Each company's text is converted into 384 numbers — a vector — that\n"
            "captures its meaning. Similar meanings get similar numbers. We embed the\n"
            "question the same way and return whatever's closest.[/]",
            border_style=C_DIM,
            padding=(1, 2),
        )
    )

    with console.status("[cyan]Loading embedding model…", spinner="dots"):
        get_model()

    for query in [
        "companies that make computer chips",
        "streaming and entertainment",
        "electric cars",
    ]:
        show_search(query)
        Prompt.ask(f"  [{C_DIM}]press enter to continue[/]", default="", show_default=False)


# --------------------------------------------------------------------- RAG

def demo_rag() -> None:
    banner()
    console.print(Rule("[bold]RAG — RETRIEVAL-AUGMENTED GENERATION[/bold]", style=C_ACCENT))

    console.print()
    console.print(
        Panel(
            "[bold]Claude has never seen our database.[/bold]\n\n"
            "[grey58]We retrieve the relevant companies ourselves with semantic search,\n"
            "hand them to the model inside the prompt, and it answers using only\n"
            "what we gave it. That's what 'augmented' means.[/]",
            border_style=C_DIM,
            padding=(1, 2),
        )
    )

    with console.status("[cyan]Loading embedding model…", spinner="dots"):
        get_model()

    questions = [
        "Which companies make computer chips, and how are they performing today?",
        "Are any of the streaming or entertainment companies down today?",
        "Tell me about the electric vehicle company in the dataset.",
    ]

    for q in questions:
        console.print()
        console.print(
            Panel(
                Text(q, style=f"bold {C_ACCENT}", justify="center"),
                title="[bold]QUESTION[/bold]",
                border_style=C_ACCENT,
            )
        )

        # 1. RETRIEVE
        console.print()
        console.print(f"  [bold]1[/bold]  [bold]RETRIEVE[/bold]  [{C_DIM}]semantic search over MongoDB[/]")

        with console.status("[cyan]Searching…", spinner="dots"):
            companies = semantic_search(q, top_k=3)

        for c in companies:
            console.print(
                f"      [{C_ACCENT}]{c['ticker']:<6}[/] {c['name']:<30} "
                f"[{C_DIM}]score {c['score']:.3f}[/]"
            )

        # 2. AUGMENT
        console.print()
        console.print(f"  [bold]2[/bold]  [bold]AUGMENT[/bold]   [{C_DIM}]that data goes into the prompt as context[/]")
        console.print(
            f"      [{C_DIM}]{len(companies)} companies → prompt "
            f"(text found them; the numbers answer the question)[/]"
        )

        # 3. GENERATE
        console.print()
        console.print(f"  [bold]3[/bold]  [bold]GENERATE[/bold]  [{C_DIM}]Claude answers using only that context[/]")

        with console.status("[cyan]Asking Claude…", spinner="dots"):
            answer = rag_ask(q, top_k=3, quiet=True)

        if answer:
            console.print()
            console.print(
                Panel(
                    Text(answer, style="white"),
                    title=f"[bold {C_OK}]ANSWER[/]",
                    subtitle=f"[{C_DIM}]sources: {', '.join(c['ticker'] for c in companies)}[/]",
                    border_style=C_OK,
                    padding=(1, 2),
                )
            )

        Prompt.ask(f"\n  [{C_DIM}]press enter to continue[/]", default="", show_default=False)


# ---------------------------------------------------------------- ASK MODE

def interactive_ask() -> None:
    """Let the audience ask their own question. Risky, but it lands."""
    banner()
    console.print(Rule("[bold]ASK THE DATABASE[/bold]", style=C_ACCENT))

    with console.status("[cyan]Loading embedding model…", spinner="dots"):
        get_model()

    console.print()
    console.print(f"  [{C_DIM}]Ask anything about the twelve companies. Blank line to exit.[/]")

    while True:
        console.print()
        q = Prompt.ask(f"  [{C_ACCENT}]?[/]")

        if not q.strip():
            break

        with console.status("[cyan]Thinking…", spinner="dots"):
            companies = semantic_search(q, top_k=3)
            answer = rag_ask(q, top_k=3, quiet=True)

        if answer:
            console.print()
            console.print(
                Panel(
                    Text(answer, style="white"),
                    border_style=C_OK,
                    subtitle=f"[{C_DIM}]sources: {', '.join(c['ticker'] for c in companies)}[/]",
                    padding=(1, 2),
                )
            )


# -------------------------------------------------------------------- MENU

def menu() -> None:
    while True:
        banner()

        table = Table(box=None, padding=(0, 3), show_header=False)
        table.add_column(style=f"bold {C_ACCENT}")
        table.add_column()
        table.add_column(style=C_DIM)

        table.add_row("1", "ETL Pipeline", "API → MongoDB → JSON → S3")
        table.add_row("2", "Semantic Search", "keyword vs meaning")
        table.add_row("3", "RAG", "ask questions in plain English")
        table.add_row("4", "Ask your own question", "live")
        table.add_row("q", "Quit", "")

        console.print(table)
        console.print()

        choice = Prompt.ask(
            f"  [{C_ACCENT}]select[/]", choices=["1", "2", "3", "4", "q"], show_choices=False
        )

        if choice == "q":
            console.print(f"\n  [{C_DIM}]Thanks for watching.[/]\n")
            break

        {
            "1": demo_pipeline,
            "2": demo_search,
            "3": demo_rag,
            "4": interactive_ask,
        }[choice]()

        Prompt.ask(f"\n  [{C_DIM}]press enter for the menu[/]", default="", show_default=False)


if __name__ == "__main__":
    validate_config()

    args = sys.argv[1:]

    if "--pipeline" in args:
        demo_pipeline()
    elif "--search" in args:
        demo_search()
    elif "--rag" in args:
        demo_rag()
    elif "--ask" in args:
        interactive_ask()
    else:
        menu()