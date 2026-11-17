from django import forms
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.models import Group

from .models import FluxoPadrao, Setor, Usuario


class LoginForm(forms.Form):
    username = forms.CharField(
        max_length=150,
        label="Usuário",
        widget=forms.TextInput(attrs={"placeholder": "Digite seu usuário"})
    )
    password = forms.CharField(
        label="Senha",
        widget=forms.PasswordInput(attrs={"placeholder": "Digite sua senha"})
    )


class EmpresaFormMixin:
    """Recebe a empresa do usuário logado e limita os selects aos dados dela."""

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.empresa = empresa
        if "setor" in self.fields:
            self.fields["setor"].queryset = Setor.objects.filter(empresa=empresa).order_by("nome")


class UsuarioCreateForm(EmpresaFormMixin, UserCreationForm):
    email = forms.EmailField(required=True, label="E-mail")
    setor = forms.ModelChoiceField(queryset=Setor.objects.none(), required=False, label="Setor")
    perfil = forms.ChoiceField(choices=Usuario._meta.get_field('perfil').choices, label="Perfil")
    grupo = forms.ModelChoiceField(queryset=Group.objects.all(), required=False, label="Grupo")

    class Meta:
        model = Usuario
        fields = ['username', 'email', 'first_name', 'last_name', 'password1', 'password2', 'setor', 'perfil', 'grupo']

    def save(self, commit=True):
        user = super().save(commit=False)
        user.empresa = self.empresa
        user.email = self.cleaned_data['email']
        user.setor = self.cleaned_data['setor']
        user.perfil = self.cleaned_data['perfil']

        if commit:
            user.save()
            if self.cleaned_data.get('grupo'):
                user.groups.add(self.cleaned_data['grupo'])
        return user


class UsuarioEditForm(EmpresaFormMixin, forms.ModelForm):
    class Meta:
        model = Usuario
        fields = ['username', 'email', 'first_name', 'last_name', 'setor', 'perfil', 'is_active', 'groups']

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        for field in self.fields.values():
            field.required = False
        self.fields['groups'].label = 'Grupos'
        self.fields['is_active'].label = 'Ativo'

    def clean_username(self):
        username = self.cleaned_data.get('username')
        if not username:
            return self.instance.username
        if Usuario.objects.exclude(pk=self.instance.pk).filter(username=username).exists():
            raise forms.ValidationError('Este nome de usuário já está em uso.')
        return username

    def clean_perfil(self):
        return self.cleaned_data.get('perfil') or self.instance.perfil


class SetorForm(EmpresaFormMixin, forms.ModelForm):
    class Meta:
        model = Setor
        fields = ['nome', 'descricao']

    def clean_nome(self):
        nome = self.cleaned_data['nome']
        qs = Setor.objects.filter(empresa=self.empresa, nome__iexact=nome)
        if self.instance.pk:
            qs = qs.exclude(pk=self.instance.pk)
        if qs.exists():
            raise forms.ValidationError('Já existe um setor com este nome.')
        return nome


class FluxoPadraoForm(forms.ModelForm):
    class Meta:
        model = FluxoPadrao
        fields = ['nome', 'descricao']
        widgets = {
            'nome': forms.TextInput(attrs={'class': 'form-control'}),
            'descricao': forms.Textarea(attrs={'class': 'form-control', 'rows': 3}),
        }


class InstanciaFluxoForm(forms.Form):
    fluxo_padrao = forms.ModelChoiceField(queryset=FluxoPadrao.objects.none(), widget=forms.Select(attrs={'class': 'form-control'}))
    nome_instancia = forms.CharField(max_length=200, widget=forms.TextInput(attrs={'class': 'form-control'}))

    def __init__(self, *args, empresa=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["fluxo_padrao"].queryset = FluxoPadrao.objects.filter(empresa=empresa).order_by("nome")
