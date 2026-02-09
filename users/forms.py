from django import forms
from django.contrib.auth.forms import UserCreationForm, AuthenticationForm
from .models import User
from menu.models import MenuItem


class CustomUserCreationForm(UserCreationForm):
    email = forms.EmailField(required=True, label='Email')
    phone = forms.CharField(max_length=15, required=False, label='Телефон')

    role = forms.ChoiceField(
        choices=User.ROLE_CHOICES,
        required=True,
        label='Роль'
    )

    class Meta:
        model = User
        fields = ('username', 'email', 'phone', 'role', 'password1', 'password2')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        # Bootstrap styling for all fields
        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' form-control').strip()

        # role is select - keep bootstrap but don't force password type
        if 'role' in self.fields:
            self.fields['role'].widget.attrs.update({'class': 'form-select'})

        # IMPORTANT: ensure correct input types for password toggling
        self.fields['password1'].widget.input_type = 'password'
        self.fields['password2'].widget.input_type = 'password'

        # Small UX tweaks
        self.fields['username'].widget.attrs.setdefault('autocomplete', 'username')
        self.fields['email'].widget.attrs.setdefault('autocomplete', 'email')
        self.fields['phone'].widget.attrs.setdefault('autocomplete', 'tel')
        self.fields['password1'].widget.attrs.setdefault('autocomplete', 'new-password')
        self.fields['password2'].widget.attrs.setdefault('autocomplete', 'new-password')



class CustomAuthenticationForm(AuthenticationForm):
    username = forms.CharField(label='Имя пользователя или Email')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' form-control').strip()

        # IMPORTANT: ensure correct input type for password toggling on login form
        if 'password' in self.fields:
            self.fields['password'].widget.input_type = 'password'
            self.fields['password'].widget.attrs.setdefault('autocomplete', 'current-password')


class ProfileUpdateForm(forms.ModelForm):
    avoid_allergens = forms.MultipleChoiceField(
        choices=MenuItem.ALLERGENS,
        required=False,
        widget=forms.CheckboxSelectMultiple,
        label='Какие аллергены исключить'
    )

    class Meta:
        model = User
        # В профиле клиента оставляем только базовые поля.
        # Аллергии/предпочтения не редактируются из профиля.
        fields = ('email', 'phone', 'first_name', 'last_name')

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        for field in self.fields.values():
            existing = field.widget.attrs.get('class', '')
            field.widget.attrs['class'] = (existing + ' form-control').strip()
