from django.contrib import admin
from .models import Category, MenuItem, Review, Order, OrderItem, DailyMenu


@admin.register(Category)
class CategoryAdmin(admin.ModelAdmin):
    list_display = ('name', 'order', 'description_short')
    list_editable = ('order',)
    search_fields = ('name', 'description')
    ordering = ('order',)

    def description_short(self, obj):
        return obj.description[:50] + '...' if len(obj.description) > 50 else obj.description

    description_short.short_description = 'Описание'


@admin.register(MenuItem)
class MenuItemAdmin(admin.ModelAdmin):
    list_display = ('name', 'category', 'price', 'is_available', 'calories', 'allergens_short')
    list_filter = ('category', 'is_available', 'allergens')
    search_fields = ('name', 'description', 'allergens')
    list_editable = ('price', 'is_available')
    filter_horizontal = ()

    def allergens_short(self, obj):
        return obj.allergens[:30] + '...' if len(obj.allergens) > 30 else obj.allergens

    allergens_short.short_description = 'Аллергены'


class OrderItemInline(admin.TabularInline):
    model = OrderItem
    extra = 0
    readonly_fields = ('item', 'quantity', 'price')
    can_delete = False


@admin.register(Order)
class OrderAdmin(admin.ModelAdmin):
    list_display = ('id', 'user', 'total_amount', 'status', 'created_at', 'items_count')
    list_filter = ('status', 'created_at')
    search_fields = ('user__username', 'user__email')
    readonly_fields = ('created_at', 'updated_at')
    inlines = [OrderItemInline]

    def items_count(self, obj):
        return obj.orderitem_set.count()

    items_count.short_description = 'Количество позиций'


@admin.register(Review)
class ReviewAdmin(admin.ModelAdmin):
    list_display = ('user', 'item', 'rating', 'comment_short', 'created_at')
    list_filter = ('rating', 'created_at')
    search_fields = ('user__username', 'item__name', 'comment')
    readonly_fields = ('created_at',)

    def comment_short(self, obj):
        return obj.comment[:50] + '...' if len(obj.comment) > 50 else obj.comment

    comment_short.short_description = 'Комментарий'


@admin.register(OrderItem)
class OrderItemAdmin(admin.ModelAdmin):
    list_display = ('order', 'item', 'quantity', 'price', 'subtotal')
    list_filter = ('order__status',)
    search_fields = ('order__id', 'item__name')

    def subtotal(self, obj):
        return obj.quantity * obj.price

    subtotal.short_description = 'Сумма'


@admin.register(DailyMenu)
class DailyMenuAdmin(admin.ModelAdmin):
    list_display = ("date",)
    filter_horizontal = ("breakfast_items", "lunch_items")
