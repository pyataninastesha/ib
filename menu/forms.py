from django import forms
from .models import Review, Category
from django.core.exceptions import ValidationError
from .services import has_ingredients
from .models import DailyMenu, MenuItem




class ReviewForm(forms.ModelForm):
    class Meta:
        model = Review
        fields = ['rating', 'comment']
        widgets = {
            'comment': forms.Textarea(attrs={'rows': 4, 'placeholder': 'Оставьте ваш отзыв...'}),
        }


class StockAdjustForm(forms.Form):
    amount = forms.DecimalField(min_value=0, decimal_places=2, max_digits=12, label="Количество")
    note = forms.CharField(required=False, max_length=255, label="Комментарий (необязательно)")


class DailyMenuForm(forms.ModelForm):
    breakfast_items = forms.ModelMultipleChoiceField(
        queryset=MenuItem.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Блюда на завтрак",
    )
    lunch_items = forms.ModelMultipleChoiceField(
        queryset=MenuItem.objects.none(),
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label="Блюда на обед",
    )

    class Meta:
        model = DailyMenu
        fields = ["breakfast_items", "lunch_items"]
        widgets = {
            "date": forms.DateInput(attrs={"type": "date", "class": "form-control"})
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # берём категории по order
        breakfast_cat = Category.objects.filter(order=1).first()
        lunch_cat = Category.objects.filter(order=2).first()

        # 2) пробуем по названию
        if not breakfast_cat:
            breakfast_cat = Category.objects.filter(name__icontains="завтр").first()
        if not lunch_cat:
            lunch_cat = Category.objects.filter(name__icontains="обед").first()

        # 3) берём первые две категории
        cats = list(Category.objects.all().order_by("order", "id"))
        if not breakfast_cat and len(cats) >= 1:
            breakfast_cat = cats[0]
        if not lunch_cat and len(cats) >= 2:
            lunch_cat = cats[1]

        self.fields["breakfast_items"].queryset = (
            MenuItem.objects.filter(category=breakfast_cat, is_available=True).order_by("name")
            if breakfast_cat else MenuItem.objects.none()
        )

        self.fields["lunch_items"].queryset = (
            MenuItem.objects.filter(category=lunch_cat, is_available=True).order_by("name")
            if lunch_cat else MenuItem.objects.none()
        )

    def clean(self):
        cleaned = super().clean()

        for field in ("breakfast_items", "lunch_items"):
            items = cleaned.get(field) or []
            for item in items:
                if not has_ingredients(item):
                    raise ValidationError(
                        f"Блюдо «{item.name}» нельзя добавить в меню дня — недостаточно ингредиентов на складе."
                    )
        return cleaned