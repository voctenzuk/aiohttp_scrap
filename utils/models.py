from tortoise import fields
from tortoise.models import Model


class Item(Model):
    url = fields.CharField(pk=True, max_length=255)
    brand = fields.TextField()
    vendor_code = fields.CharField(max_length=255, null=True)
    name = fields.TextField()
    image = fields.TextField(
        default="https://yugcleaning.ru/wp-content/themes/consultix/images/no-image-found-360x250.png"
    )
    gender = fields.TextField()
    category = fields.TextField()
    subcategory = fields.TextField()
    color = fields.TextField(null=True)
    standard_price = fields.FloatField()
    sale_price = fields.FloatField()
    discount = fields.FloatField()
    available_sizes = fields.TextField()
    size_label = fields.CharField(max_length=100, null=True)
    last_update = fields.DatetimeField(auto_now=True)
    created = fields.DatetimeField(auto_now_add=True)

    def __str__(self):
        return self.name
