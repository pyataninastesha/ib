from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User
from core.models import Organization
from menu.models import MenuItem


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email')
    phone = forms.CharField(max_length=15, required=False, label='Телефон')

    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        required=True,
        label='Роль'
    )

    org_action = forms.ChoiceField(
        choices=(('create', 'Создать организацию (для Eco-менеджера)'), ('join', 'Присоединиться по коду')),
        required=True,
        label='Организация',
        widget=forms.Select
    )
    org_name = forms.CharField(max_length=200, required=False, label='Название организации')
    org_type = forms.ChoiceField(choices=Organization.ORG_TYPES, required=False, label='Тип заведения')
    org_goals = forms.CharField(max_length=250, required=False, label='Цели (через запятую)')
    avg_portions_per_day = forms.IntegerField(required=False, min_value=0, label='Среднее порций в день')
    join_code = forms.CharField(max_length=12, required=False, label='Код подключения')

    class Meta:
        model = User
        fields = ('username', 'email', 'phone', 'role', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        # Bootstrap styling
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' form-control').strip()

        if 'role' in self.fields:
            self.fields['role'].widget.attrs.update({'class': 'form-select'})
        if 'org_action' in self.fields:
            self.fields['org_action'].widget.attrs.update({'class': 'form-select'})
        if 'org_type' in self.fields:
            self.fields['org_type'].widget.attrs.update({'class': 'form-select'})

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get('role')
        org_action = cleaned.get('org_action')

        # Eco-менеджер создаёт организацию
        if role == 'admin':
            cleaned['org_action'] = 'create'
            if not cleaned.get('org_name'):
                self.add_error('org_name', 'Укажите название организации')
            if not cleaned.get('org_type'):
                self.add_error('org_type', 'Выберите тип заведения')
        else:
            # остальные присоединяются по коду
            cleaned['org_action'] = 'join'
            if not cleaned.get('join_code'):
                self.add_error('join_code', 'Введите код подключения от вашей организации')

        return cleaned

    def save(self, commit=True):
        user = super().save(commit=False)
        role = self.cleaned_data.get('role')
        organization = None

        if role == 'admin':
            # создать организацию и сгенерировать код подключения
            join_code = Organization.generate_join_code()
            organization = Organization.objects.create(
                name=self.cleaned_data.get('org_name') or 'Организация',
                org_type=self.cleaned_data.get('org_type') or 'other',
                goals=self.cleaned_data.get('org_goals') or '',
                avg_portions_per_day=self.cleaned_data.get('avg_portions_per_day') or 0,
                join_code=join_code,
            )
        else:
            code = (self.cleaned_data.get('join_code') or '').strip().upper()
            organization = Organization.objects.filter(join_code=code).first()

        user.organization = organization
        user.role = role

        if commit:
            user.save()
        return user


class CustomAuthenticationForm(AuthenticationForm):
    """Login form with consistent styling."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' form-control').strip()


class ProfileUpdateForm(forms.ModelForm):
    """User profile update (safe editable fields only)."""

    class Meta:
        model = User
        fields = ('email', 'phone')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' form-control').strip()
