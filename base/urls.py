from django.urls import path

from . import views

app_name = 'base'

urlpatterns = [
    path('', views.index, name='index'),
    path('gestion', views.gestion, name='gestion'),
    path('statistiques', views.otherstats, name='otherstats'),
    path('achats', views.pre_achats, name='pre_achats'),
    path('achats/<int:household_id>', views.achats, name='achats'),
    path('produits', views.ProductsListView.as_view(), name='products'),
    path('export/produits', views.export_products, name='export_products'),
    path('produit/<int:product_id>', views.detail_product, name='detail_product'),
    path('archiver_produit/<int:product_id>', views.archive_product, name='archive_product'),
    path('historique_produit/<int:product_id>', views.product_history, name='product_history'),
    path('produit', views.create_product, name='create_product'),
    path('membres', views.members, name='members'),
    path('export/foyers', views.export_households, name='export_households'),
    path('membresstats', views.menbersstats, name='membersstats'),
    path('membre/<int:pk>', views.HouseholdUpdate.as_view(), name='detail_member'),
    path('membre', views.HouseholdCreate.as_view(), name='create_household'),
    path('archiver_foyer/<int:household_id>', views.archive_household, name='archive_household'),
    path('fournisseurs', views.providers, name='providers'),
    path('export/fournisseurs', views.export_providers, name='export_providers'),
    path('fournisseur/<int:provider_id>', views.detail_provider, name='detail_provider'),
    path('fournisseur/<int:provider_id>/produits', views.ProviderProductsListView.as_view(), name='provider_products_list'),
    path('fournisseur', views.create_provider, name='create_provider'),
    path('appro', views.pre_appro, name='pre_appro'),
    path('appro/<int:provider_id>', views.ApproView.as_view(), name='appro'),
    path('approslist', views.approslist, name='approslist'),
    path('compte', views.pre_compte, name='pre_compte'),
    path('compte/<int:household_id>', views.compte, name='compte'),
    path('compteslist', views.compteslist, name='compteslist'),
    path('inventaire', views.inventory, name='inventory'),
    path('ecarts', views.ecarts, name='ecarts'),
    path('export/inventaires', views.export_inventory, name='export_inventory'),
    path('stats/<int:product_id>', views.stats, name='stats'),
    path('database', views.database_info, name='database_info'),
    path('notes', views.notes, name='notes'),
    path('note', views.create_note, name='create_note'),
    path('note/<int:note_id>', views.detail_note, name='detail_note'),
    path('stockslist', views.stockslist, name='stockslist'),
    path('mailslist', views.mailslist, name='mailslist'),
    path('mails_send_all', views.mails_send_all, name='mails_send_all'),
    path('mails_del_send', views.mails_del_send, name='mails_del_send'),
    path('mails_del_all', views.mails_del_all, name='mails_del_all'),
    path('mail_del/<int:mail_id>', views.mail_del, name='mail_del'),
    path('mail_send/<int:mail_id>', views.mail_send, name='mail_send'),
    path('subscriptionslist', views.subscriptionslist, name='subscriptionslist'),
    path('purchaseslist', views.purchaseslist, name='purchaseslist'),
    path('valueslist', views.valueslist, name='valueslist'),
    path('activité/<int:perm_id>', views.activity_details, name='activity_details'),

]
