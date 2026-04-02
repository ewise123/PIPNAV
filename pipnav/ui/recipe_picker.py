"""Recipe picker modal — select a launch recipe to execute."""

from __future__ import annotations

from dataclasses import dataclass

from textual import on
from textual.app import ComposeResult
from textual.containers import Vertical
from textual.message import Message
from textual.screen import ModalScreen
from textual.widgets import OptionList, Static
from textual.widgets.option_list import Option

from pipnav.core.profiles import LaunchRecipe


class RecipePicker(ModalScreen):
    """Modal for selecting a launch recipe."""

    DEFAULT_CSS = """
    RecipePicker {
        align: center middle;
    }
    RecipePicker #recipe-container {
        width: 56;
        height: auto;
        max-height: 70%;
        border: solid $primary;
        background: $surface;
        color: $primary;
        padding: 1 2;
    }
    RecipePicker OptionList {
        background-tint: initial;
        height: auto;
        max-height: 20;
    }
    RecipePicker OptionList:focus {
        background-tint: initial;
    }
    """

    BINDINGS = [
        ("escape", "dismiss", "Close"),
    ]

    @dataclass
    class Selected(Message):
        """Fired when a recipe is selected."""

        recipe: LaunchRecipe

    def __init__(self, recipes: tuple[LaunchRecipe, ...]) -> None:
        super().__init__()
        self._recipes = recipes

    def compose(self) -> ComposeResult:
        with Vertical(id="recipe-container"):
            yield Static("[bold]LAUNCH RECIPES[/]\n")
            yield OptionList(id="recipe-options")

    def on_mount(self) -> None:
        option_list = self.query_one("#recipe-options", OptionList)
        for recipe in self._recipes:
            label = (
                f"  {recipe.display_label}\n"
                f"  [dim]{recipe.description}[/]"
            )
            option_list.add_option(Option(label, id=recipe.name))

        if not self._recipes:
            option_list.add_option(Option("  [dim]No recipes available[/]"))

        option_list.focus()

    @on(OptionList.OptionSelected, "#recipe-options")
    def _on_selected(self, event: OptionList.OptionSelected) -> None:
        if event.option_index is not None and 0 <= event.option_index < len(self._recipes):
            self.dismiss()
            self.post_message(self.Selected(self._recipes[event.option_index]))

    def action_dismiss(self) -> None:
        self.dismiss()
