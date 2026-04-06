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

# Special option IDs
_CUSTOM_ID = "__custom__"
_NEW_RECIPE_ID = "__new_recipe__"
_SEPARATOR_ID = "__sep__"


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

    @dataclass
    class CustomRequested(Message):
        """Fired when the user picks Custom launch."""

        pass

    @dataclass
    class NewRecipeRequested(Message):
        """Fired when the user picks New Recipe."""

        pass

    def __init__(self, recipes: tuple[LaunchRecipe, ...]) -> None:
        super().__init__()
        self._recipes = recipes

    def compose(self) -> ComposeResult:
        with Vertical(id="recipe-container"):
            yield Static("[bold]LAUNCH RECIPES[/]  [dim]a:pick  Esc:close[/]\n")
            yield OptionList(id="recipe-options")

    def on_mount(self) -> None:
        option_list = self.query_one("#recipe-options", OptionList)

        for recipe in self._recipes:
            label = (
                f"  {recipe.display_label}\n"
                f"  [dim]{recipe.description}[/]"
            )
            option_list.add_option(Option(label, id=recipe.name))

        # Separator and special options
        option_list.add_option(Option("  [dim]───────────────────────────[/]", id=_SEPARATOR_ID))
        option_list.add_option(
            Option(
                "  [bold]*[/] Custom Launch...\n"
                "  [dim]Configure all options before launching[/]",
                id=_CUSTOM_ID,
            )
        )
        option_list.add_option(
            Option(
                "  [bold]+[/] New Recipe...\n"
                "  [dim]Create and save a new recipe[/]",
                id=_NEW_RECIPE_ID,
            )
        )

        option_list.focus()

    @on(OptionList.OptionSelected, "#recipe-options")
    def _on_selected(self, event: OptionList.OptionSelected) -> None:
        option = event.option
        if option.id == _SEPARATOR_ID:
            return  # Ignore separator clicks
        if option.id == _CUSTOM_ID:
            self.dismiss()
            self.post_message(self.CustomRequested())
        elif option.id == _NEW_RECIPE_ID:
            self.dismiss()
            self.post_message(self.NewRecipeRequested())
        elif event.option_index is not None and event.option_index < len(self._recipes):
            self.dismiss()
            self.post_message(self.Selected(self._recipes[event.option_index]))

    def action_dismiss(self) -> None:
        self.dismiss()
