import uuid

from django import forms
from django.conf import settings
from django.urls import reverse_lazy
from django.utils.translation import pgettext_lazy
from django_prices.forms import PriceField

from ...core.forms import (
    AjaxSelect2ChoiceField, AjaxSelect2MultipleChoiceField)
from ...discount.models import Sale, Voucher
from ...product.models import Product
from ...shipping.models import ShippingMethodCountry, COUNTRY_CODE_CHOICES


class SaleForm(forms.ModelForm):
    products = AjaxSelect2MultipleChoiceField(
        queryset=Product.objects.all(),
        fetch_data_url=reverse_lazy('dashboard:ajax-products'), required=True)

    class Meta:
        model = Sale
        exclude = []
        labels = {
            'name': pgettext_lazy(
                'Sale (discount) field',
                'Sale\'s name'),
            'type': pgettext_lazy(
                'Sale (discount) field',
                'Type of products related to the sale'),
            'value': pgettext_lazy(
                'Sale (discount) field',
                'Value'),
            'products': pgettext_lazy(
                'Sale (discount) field',
                'Products in sale'),
            'categories': pgettext_lazy(
                'Sale (discount) field',
                'Sale\'s categories'),
        }

    def __init__(self, *args, **kwargs):
        super(SaleForm, self).__init__(*args, **kwargs)
        if self.instance.pk:
            self.fields['products'].set_initial(self.instance.products.all())

    def clean(self):
        cleaned_data = super(SaleForm, self).clean()
        discount_type = cleaned_data['type']
        value = cleaned_data['value']
        if discount_type == Sale.PERCENTAGE and value > 100:
            self.add_error('value', pgettext_lazy(
                'Sale (discount) error',
                'Sale cannot exceed 100%'))
        return cleaned_data


class VoucherForm(forms.ModelForm):

    class Meta:
        model = Voucher
        exclude = ['limit', 'apply_to', 'product', 'category']
        labels = {
            'type': pgettext_lazy(
                'Voucher field',
                'Discount type'),
            'name': pgettext_lazy(
                'Voucher field',
                'Voucher\'s name'),
            'code': pgettext_lazy(
                'Voucher field',
                'Voucher code'),
            'usage_limit': pgettext_lazy(
                'Voucher field',
                'Limit for using the voucher'),
            'used': pgettext_lazy(
                'Voucher field',
                'Number of voucher usages'),
            'start_date': pgettext_lazy(
                'Voucher field',
                'Date voucher starts being valid'),
            'end_date': pgettext_lazy(
                'Voucher field',
                'Date voucher stops being valid'),
        }

    def __init__(self, *args, **kwargs):
        initial = kwargs.get('initial', {})
        instance = kwargs.get('instance')
        if instance and instance.id is None and not initial.get('code'):
            initial['code'] = self._generate_code
        kwargs['initial'] = initial
        super(VoucherForm, self).__init__(*args, **kwargs)

    def _generate_code(self):
        while True:
            code = str(uuid.uuid4()).replace('-', '').upper()[:12]
            if not Voucher.objects.filter(code=code).exists():
                return code


def country_choices():
    country_codes = ShippingMethodCountry.objects.all()
    country_codes = country_codes.values_list('country_code', flat=True)
    country_codes = country_codes.distinct()
    country_dict = dict(COUNTRY_CODE_CHOICES)
    return [
        (country_code, country_dict[country_code])
        for country_code in country_codes]


class ShippingVoucherForm(forms.ModelForm):

    limit = PriceField(
        min_value=0, required=False, currency=settings.DEFAULT_CURRENCY)
    apply_to = forms.ChoiceField(
        choices=country_choices,
        required=False)

    class Meta:
        model = Voucher
        fields = ['apply_to', 'limit']
        labels = {
            'apply_to': pgettext_lazy(
                'Shipping voucher form label for `apply_to` field',
                'Country'),
            'limit': pgettext_lazy(
                'Shipping voucher form label for `limit` field',
                'Only if order is over or equal to'),
        }

    def save(self, commit=True):
        self.instance.category = None
        self.instance.product = None
        return super(ShippingVoucherForm, self).save(commit)


class ValueVoucherForm(forms.ModelForm):

    limit = PriceField(
        min_value=0, required=False, currency=settings.DEFAULT_CURRENCY)

    class Meta:
        model = Voucher
        fields = ['limit']
        labels = {
            'limit': pgettext_lazy(
                'Value voucher form label for `limit` field',
                'Only if purchase value is greater than or equal to'),
        }

    def save(self, commit=True):
        self.instance.category = None
        self.instance.apply_to = None
        self.instance.product = None
        return super(ValueVoucherForm, self).save(commit)


class CommonVoucherForm(forms.ModelForm):

    use_required_attribute = False
    apply_to = forms.ChoiceField(
        choices=Voucher.APPLY_TO_PRODUCT_CHOICES, required=False)

    def __init__(self, *args, **kwargs):
        super(CommonVoucherForm, self).__init__(*args, **kwargs)

    def save(self, commit=True):
        self.instance.category = None
        self.instance.limit = None
        # Apply to one with percentage discount is more complicated case.
        # On which product we should apply it? On first, last or cheapest?
        # Percentage case is limited to the all value and the apply_to field
        # is not used in this case so we set it to None.
        if (self.instance.discount_value_type ==
                Voucher.DISCOUNT_VALUE_PERCENTAGE):
            self.instance.apply_to = None
        return super(CommonVoucherForm, self).save(commit)


class ProductVoucherForm(CommonVoucherForm):
    product = AjaxSelect2ChoiceField(
        queryset=Product.objects.all(),
        fetch_data_url=reverse_lazy('dashboard:ajax-products'),
        required=True)

    class Meta:
        model = Voucher
        fields = ['product', 'apply_to']
        labels = {
            'apply_to': pgettext_lazy(
                'Shipping voucher form label for `apply_to` field',
                'Country'),
            'product': pgettext_lazy(
                'Voucher field',
                'product'),
        }

    def __init__(self, *args, **kwargs):
        super(ProductVoucherForm, self).__init__(*args, **kwargs)
        if self.instance.product:
            self.fields['product'].set_initial(self.instance.product)


class CategoryVoucherForm(CommonVoucherForm):

    class Meta:
        model = Voucher
        fields = ['category', 'apply_to']
        labels = {
            'apply_to': pgettext_lazy(
                'Shipping voucher form label for `apply_to` field',
                'Country'),
            'category': pgettext_lazy(
                'Voucher field',
                'category'),
        }

    def __init__(self, *args, **kwargs):
        super(CategoryVoucherForm, self).__init__(*args, **kwargs)
        self.fields['category'].required = True
