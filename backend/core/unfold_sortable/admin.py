from adminsortable2.admin import SortableAdminMixin

from core.unfold_sortable.forms import MovePageActionForm


class UnfoldSortableAdminMixin(SortableAdminMixin):
    action_form = MovePageActionForm
