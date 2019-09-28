import smtplib, ssl
import json, datetime
from decimal import Decimal

from django.shortcuts import render
from django.http import HttpResponse, HttpResponseRedirect
from django.urls import reverse, reverse_lazy
from django.contrib import messages
from django.core.mail import send_mail
from django.views.generic.edit import CreateView, UpdateView
from django.db import transaction
from django.db.models import Sum

from .models import *
from .forms import *
from .templatetags.my_tags import *
from compteur.settings import DEFAULT_FROM_EMAIL

def get_local_settings():
    localsettings = LocalSettings.objects.first()
    if localsettings is None:
        localsettings = LocalSettings.objects.create()
    return localsettings

def my_send_mail(request, subject, message, recipient_list, success_msg, error_msg):
    if recipient_list:
        try:
            send_mail('[Compteur de GASE] ' + subject, message, DEFAULT_FROM_EMAIL, recipient_list, fail_silently=False)
            messages.success(request, '✔ ' + success_msg)
        except:
            messages.error(request, '✘ ' + error_msg)

### index

def index(request):
    txt_home = get_local_settings().txt_home
    
    note_not_read=len([p for p in Note.objects.all() if not p.read])
    if note_not_read > 1:
        note_pluralize = "s"
    else:
        note_pluralize = ""
        
    action_not_done=len([p for p in Note.objects.all() if not p.action])
    if action_not_done > 1:
        action_pluralize = "s"
    else:
        action_pluralize = ""
    
    txt_message = "Il y a actuellement {0:d} message{1:s} non lu{1:s} et {2:d} action{3:s} non réalisée{3:s}.".format(note_not_read, note_pluralize, action_not_done, action_pluralize)
    
    return render(request, 'base/index.html', {'txt_home': txt_home, 'txt_message': txt_message})

def gestion(request):
    
    # todo : use aggregate ?
    value_stock=sum([p.value_stock() for p in Product.objects.all()])
    value_accounts=sum([p.account for p in Household.objects.all()])
    alert_pdts=[p for p in Product.objects.filter(stock_alert__isnull=False, visible=True).order_by('name') if p.stock < p.stock_alert]
    value_appro=sum([p.amount for p in ApproCompteOp.objects.all()])
    value_purchase=sum([p.cost_of_purchase() for p in ChangeStockOp.objects.filter(label="ApproStock")])

    return render(request, 'base/gestion.html',
                  {'value_stock': value_stock,
                   'value_accounts': value_accounts,
                   'diff_values': value_accounts - value_stock,
                   'alert_pdts': alert_pdts,
                   'value_appro': value_appro,
                   'value_purchase': value_purchase
                  })


### achats

def pre_achats(request):
    if request.method == 'POST':
        form = HouseholdList(request.POST)
        if form.is_valid():
            return HttpResponseRedirect(reverse('base:achats', args=(request.POST['household'],)))
    else:
        form = HouseholdList()
    return render(request, 'base/pre_achats.html', {'form': form})

def achats(request, household_id):
    household = Household.objects.get(pk=household_id)
    if request.method == 'POST':
        s = 0
        msg = "Voici votre ticket de caisse :\n"
        purchase = Purchase(household=household)
        purchase.save()
        for p, q in request.POST.items():
            if p.startswith('basket_'):
                pdt = Product.objects.get(pk=int(p[7:]))
                q = Decimal(q)
                op = PurchaseDetailOp.create(product=pdt, purchase=purchase, quantity=-q)
                op.save()
                household.account += op.price
                household.save()
                pdt.stock -= q
                pdt.save()
                s -= op.price
                msg += "{} ({} € / unité) : {} unité  -> {} €\n".format(pdt.name, pdt.price, q, op.price)
                if (pdt.stock_alert and pdt.stock <= pdt.stock_alert):
                    ref = pdt.get_email_stock_alert()
                    if ref:
                        my_send_mail(request, subject='Alerte de stock', message='Le stock de {} est bas : il reste {} unités'.format(pdt, pdt.stock), recipient_list=ref,
                                     success_msg='Alerte stock envoyée par mail', error_msg='Erreur : l\'alerte stock n\'a pas été envoyée par mail')
        msg += "Ce qui nous donne un total de {} €.\n\nCiao!".format(s)
        messages.success(request, '✔ Votre compte a été débité de ' + str(round2(s)) + ' €')
        mails = household.get_emails_receipt()
        my_send_mail(request, subject='Ticket de caisse', message=msg, recipient_list=mails,
                     success_msg='Le ticket de caisse a été envoyé par mail', error_msg='Erreur : le ticket de caisse n\'a pas été envoyé par mail')
        return HttpResponseRedirect(reverse('base:index'))
    else:
        localsettings = get_local_settings()
        purchases_history = Purchase.objects.filter(household_id=household_id).order_by('-date')[:10]
        history = [{'date': p.date, 'details': PurchaseDetailOp.objects.filter(purchase=p)} for p in purchases_history]
        pdts = {str(p.id): {"name": p.name, "category": p.category.name,
                            "price": str(p.price), "unit": p.unit.name, "vrac": p.unit.vrac}
                for p in Product.objects.filter(visible=True)}
        pdts = json.dumps(pdts)
        print(household.account - localsettings.min_account)
        context = {'household': household,
                   'cats': Category.objects.all(),
                   'max_amount': household.account - localsettings.min_account,
                   'pdts': pdts,
                   'history':history}
        return render(request, 'base/achats.html', context)

### compte

def pre_compte(request):
    if request.method == 'POST':
        form = HouseholdList(request.POST)
        if form.is_valid():
            return HttpResponseRedirect(reverse('base:compte', args=(request.POST['household'],)))
    else:
        form = HouseholdList()
    return render(request, 'base/pre_compte.html', {'form': form})

def compte(request, household_id):
    household = Household.objects.get(pk=household_id)
    history = ApproCompteOp.objects.filter(household_id=household_id).order_by('-date')[:5]
    if request.method == 'POST':
        form = ApproCompteForm(request.POST)
        if form.is_valid():
            q = form.cleaned_data['amount']
            k = form.cleaned_data['kind']
            op = ApproCompteOp(household=household, amount=q, kind=k)
            op.save()
            household.account += q
            household.save()
            messages.success(request, '✔ Approvisionnement du compte effectué')
            msg = 'Votre compte a été approvisionné de {} €'.format(q)
            mails = household.get_emails_receipt()
            my_send_mail(request, subject='Ticket de caisse', message=msg, recipient_list=mails,
                         success_msg='Le ticket de caisse a été envoyé par mail', error_msg='Erreur : le ticket de caisse n\'a pas été envoyé par mail')
            return HttpResponseRedirect(reverse('base:index'))
    else:
        form = ApproCompteForm()
    context = {'household': household,
               'form': form,
               'history': history,
               'number': household.get_formated_number()
    }
    return render(request, 'base/compte.html', context)
    
def compteslist(request):
    columns = ['jour', 'mois', 'année', 'foyer', 'approvisionnement', 'type']
    comptes = [{"jour": p.date.day, "mois": p.date.month, "année": p.date.year, "foyer": str(p.household), "approvisionnement": '{} €'.format(p.amount), "type": p.get_kind_display()} 
              for p in ApproCompteOp.objects.all()]
    columns = json.dumps(columns)
    comptes = json.dumps(comptes)
    return render(request, 'base/compteslist.html', {'columns': columns, 'comptes': comptes})


### produits

def create_product(request):
    if request.method == 'POST':
        form = ProductForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '✔ Produit créé !')
            return HttpResponseRedirect(reverse('base:products'))
    else:
        form = ProductForm()
    return render(request, 'base/product.html', {'form': form})

def detail_product(request, product_id):
    pdt = Product.objects.get(pk=product_id)
    if request.method == 'POST':
        form = ProductForm(request.POST, instance=pdt)
        if form.is_valid():
            form.save()
            messages.success(request, '✔ Produit mis à jour !')
            return HttpResponseRedirect(reverse('base:products'))
    else:
        form = ProductForm(instance=pdt, initial={'stock': pdt.stock, 'value': pdt.value_stock()})
    return render(request, 'base/product.html', {'form': form})

def products(request):
    columns = ['nom', 'catégorie', 'fournisseur', "prix d'achat", 'prix de vente', 'vrac', 'visible', 'stock']
    pdts = [{"id": p.id, "nom": p.name, "catégorie": str(p.category), "fournisseur": str(p.provider), "prix d'achat": '{} € / {}'.format(p.cost_of_purchase, p.unit),
             "prix de vente": '{} € / {}'.format(p.price, p.unit), "vrac": bool_to_utf8(p.unit.vrac), "visible": bool_to_utf8(p.visible), "stock": round_stock(p.stock)}
            for p in Product.objects.all()]
    columns = json.dumps(columns)
    pdts = json.dumps(pdts)
    return render(request, 'base/products.html', {'columns': columns, 'pdts': pdts})


### appro

def pre_appro(request):
    if request.method == 'POST':
        form = ProviderList(request.POST)
        if form.is_valid():
            return HttpResponseRedirect(reverse('base:appro', args=(request.POST['provider'],)))
    else:
        form = ProviderList()
    return render(request, 'base/pre_appro.html', {'form': form})

def appro(request, provider_id):
    prov = Provider.objects.get(pk=provider_id)
    pdts = prov.get_products()
    if request.method == 'POST':
        form = ProductList(pdts, request.POST)
        if form.is_valid():
            msgs = {}
            for p, q in form.cleaned_data.items():
                if q:
                    pdt = Product.objects.get(pk=p)
                    op = ChangeStockOp.create_appro_stock(product=pdt, quantity=q)
                    op.save()
                    pdt.stock += q
                    pdt.save()
                    ref = pdt.get_email_stock_alert()
                    print(ref)
                    if ref:
                        msgs[ref] = msgs.get(ref, '') + '{} a été approvisionné de {} unités\n'.format(pdt, q)
            messages.success(request, '✔ Approvisionnement effectué')
            for (key, value) in msgs.items():
                my_send_mail(request, subject='Approvisionnement', message=value, recipient_list=[key],
                             success_msg='Mail de confirmation envoyé au référent', error_msg='Erreur : le mail de confirmation n\'a pas été envoyé')
            return HttpResponseRedirect(reverse('base:index'))
    else:
        form = ProductList(pdts)
    context = {'provider': prov,
               'form': form,
    }
    return render(request, 'base/appro.html', context)
    
def approslist(request):
    columns = ['jour', 'mois', 'année', 'fournisseur', 'produit', 'coût total']
    appros = [{"jour": p.date.day, "mois": p.date.month, "année": p.date.year, "fournisseur": str(p.product.provider), "produit": str(p.product), "coût total": '{0:.2f} €'.format(p.cost_of_purchase())} 
              for p in ChangeStockOp.objects.filter(label="ApproStock")]
    columns = json.dumps(columns)
    appros = json.dumps(appros)
    return render(request, 'base/approslist.html', {'columns': columns, 'appros': appros})
    
### stock

def stockslist(request):
    columns = ['fournisseur', 'catégorie', 'produit', 'valeur totale']
    stocks = [{"fournisseur": str(p.provider), "catégorie": str(p.category), "produit": str(p), "valeur totale": '{0:.2f} €'.format(p.value_stock())} 
              for p in Product.objects.all()]
    columns = json.dumps(columns)
    stocks = json.dumps(stocks)
    return render(request, 'base/stockslist.html', {'columns': columns, 'stocks': stocks})

### membres

def members(request):
    columns = ['nom', "numéro d'adhérent", "date d'adhésion", "date de clotûre", 'foyer', 'email', 'bigophone']
    members = [{"id": p.id, "nom": p.name, "numéro d'adhérent": p.household.get_formated_number(), "date d'adhésion": p.household.date.strftime("%d/%m/%Y"), "date de clotûre": p.household.get_formated_date_closed("%d/%m/%Y"), "foyer": str(p.household), "email": p.email, "bigophone": p.tel, "household_id": p.household.id if p.household else 0}
               for p in Member.objects.all()]
    columns = json.dumps(columns)
    members = json.dumps(members)
    
    txt_number_h = str(len([p for p in Household.objects.all() if p.date_closed is None]))
    txt_number_m = str(len([p for p in Member.objects.all() if p.household.date_closed is None]))
    
    return render(request, 'base/members.html', {'columns': columns, 'members': members, 'txt_number_m': txt_number_m, 'txt_number_h': txt_number_h})

def menbersstats(request):

    # dates    
    dates = [datetime.date.today()]
    for h in Household.objects.all():
        if h.date not in dates:
            dates.append(h.date)
        if h.date_closed is not None:
            if h.date_closed not in dates:
                dates.append(h.date_closed)
    dates.sort()    
    
    # foyers
    households_stats = [0]*len(dates)    
    for h in Household.objects.all():
        for i in range(dates.index(h.date), len(dates)):
            households_stats[i] += 1
        if h.date_closed is not None:
            for i in range(dates.index(h.date_closed), len(dates)):
                households_stats[i] -= 1        
    households_data = [{'nb': str(households_stats[i]), 'date': dates[i].isoformat(), 'label': str(households_stats[i])} for i in range(len(dates))]
    
    # membres
    members_stats = [0]*len(dates)
    for m in Member.objects.all():
        for i in range(dates.index(m.household.date), len(dates)):
            members_stats[i] += 1
        if m.household.date_closed is not None:
            for i in range(dates.index(m.household.date_closed), len(dates)):
                members_stats[i] -= 1        
    members_data = [{'nb': str(members_stats[i]), 'date': dates[i].isoformat(), 'label': str(members_stats[i])} for i in range(len(dates))]
    
    # return
    return render(request, 'base/menbersstats.html', {'households_data': households_data, 'members_data': members_data})
    

class HouseholdCreate(CreateView):
    model = Household
    fields = ['number', 'name', 'address', 'comment']
    template_name = 'base/household.html'
    success_url = reverse_lazy('base:members')

    def get_initial(self):
        initial = super(HouseholdCreate, self).get_initial()
        initial['number'] = get_advised_household_number()
        return initial

    def get_context_data(self, **kwargs):
        data = super(HouseholdCreate, self).get_context_data(**kwargs)
        if self.request.POST:
            data['members'] = MemberFormSet(self.request.POST)
        else:
            data['members'] = MemberFormSet()
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        members = context['members']
        with transaction.atomic():
            form.instance.created_by = self.request.user
            if member.is_valid():
                member.instance = form.save()
                member.save()
                messages.success(self.request, '✔ Foyer créé !')
            else:
                return self.form_invalid(form)
        return super(HouseholdCreate, self).form_valid(form)


class HouseholdUpdate(UpdateView):
    model = Household
    fields = ['number', 'name', 'date_closed', 'address', 'comment']
    template_name = 'base/household.html'
    success_url = reverse_lazy('base:members')

    def get_context_data(self, **kwargs):
        data = super(HouseholdUpdate, self).get_context_data(**kwargs)
        if self.request.POST:
            data['members'] = MemberFormSet(self.request.POST, instance=self.object)
        else:
            data['members'] = MemberFormSet(instance=self.object)
        return data

    def form_valid(self, form):
        context = self.get_context_data()
        members = context['members']
        with transaction.atomic():
            form.instance.created_by = self.request.user
            if member.is_valid():
                member.instance = form.save()
                member.save()
                messages.success(self.request, '✔ Foyer mis à jour !')
            else:
                return self.form_invalid(form)
        return super(HouseholdUpdate, self).form_valid(form)


### providers

def providers(request):
    columns = ['nom', 'contact', 'commentaire']
    providers = [{"id": p.id, "nom": p.name, "contact": str(p.contact),
                  "commentaire": p.comment}
                 for p in Provider.objects.all()]
    columns = json.dumps(columns)
    providers = json.dumps(providers)
    return render(request, 'base/providers.html', {'columns': columns, 'providers': providers})

def create_provider(request):
    if request.method == 'POST':
        form = ProviderForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '✔ Produit créé !')
            return HttpResponseRedirect(reverse('base:providers'))
    else:
        form = ProviderForm()
    return render(request, 'base/provider.html', {'form': form})

def detail_provider(request, provider_id):
    provider = Provider.objects.get(pk=provider_id)
    if request.method == 'POST':
        form = ProviderForm(request.POST, instance=provider)
        if form.is_valid():
            form.save()
            messages.success(request, '✔ Fournisseur mis à jour')
            return HttpResponseRedirect(reverse('base:providers'))
    else:
        form = ProviderForm(instance=provider)
    return render(request, 'base/provider.html', {'form': form})
    
### notes
def notes(request):
    columns = ['date', 'auteur', 'message', 'message lu ?', 'action(s) réalisée(s) ?']
    notes = [{"id": p.id, "date": p.date.strftime("%d/%m/%Y"), "auteur": str(p.who), "message": p.message, 'message lu ?': bool_to_utf8(p.read), 'action(s) réalisée(s) ?': bool_to_utf8(p.action)}
             for p in Note.objects.all()]
    columns = json.dumps(columns)
    notes = json.dumps(notes)
    return render(request, 'base/notes.html', {'columns': columns, 'notes': notes})

def create_note(request):
    if request.method == 'POST':
        form = NoteForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, '✔ Message créé !')
            return HttpResponseRedirect(reverse('base:notes'))
    else:
        form = NoteForm()
    return render(request, 'base/note.html', {'form': form})

def detail_note(request, note_id):
    pdt = Note.objects.get(pk=note_id)
    print(note_id)
    if request.method == 'POST':
        form = NoteForm(request.POST, instance=pdt)
        if form.is_valid():
            form.save()
            messages.success(request, '✔ Message mis à jour !')
            return HttpResponseRedirect(reverse('base:notes'))
    else:
        form = NoteForm(instance=pdt)
    return render(request, 'base/note.html', {'form': form})

## inventaire

def inventory(request):
    pdts = Product.objects.all()
    if request.method == 'POST':
        form = ProductList(pdts, request.POST)
        if form.is_valid():
            for p, q in form.cleaned_data.items():
                pdt = Product.objects.get(pk=p)
                if q:
                    diff = q-pdt.stock
                    if diff != 0: # todo check
                        op = ChangeStockOp.create_inventory(product=pdt, quantity=diff)
                        op.save()
                        pdt.stock = q
                        pdt.save()
            messages.success(request, '✔ Stock mis à jour !')
            return HttpResponseRedirect(reverse('base:ecarts'))
    else:
        form = ProductList(pdts, request.POST)
    return render(request, 'base/inventory.html', {'form': form})

def ecarts(request):
    ope = ChangeStockOp.objects.filter(label='Inventaire')
    for o in list(ope):
        print(o.date, o.price)
    dates = {o.date.date() for o in ope} # on regroupe par jour
    dates = sorted(dates, reverse=True)[:10] # on garde les 10 derniers
    ecarts = [{'date': d,
               'details': ope.filter(date__date=d),
               'result': sum([o.price for o in ope.filter(date__date=d)])}
              for d in dates]
    return render(request, 'base/ecarts.html', {'ecarts': ecarts})


def stats(request, product_id):
    # opes = ChangeStockOp.objects.filter(product=product_id, date__date__gt=datetime.date(2018, 1, 1))
    opes = ChangeStockOp.objects.filter(product=product_id).order_by('date')
    data = [{'stock': str(a.stock), 'date': a.date.isoformat(), 'label': a.label} for a in opes ]
    pdt = Product.objects.get(pk=product_id)
    return render(request, 'base/stats.html', {'pdt': pdt, 'data': data,})


def database_info(request):
    pdts = [{'name': pdt.name, 'stock': pdt.stock,
             'computed': ChangeStockOp.objects.filter(product=pdt).aggregate(Sum('quantity'))['quantity__sum']}
            for pdt in Product.objects.all()]
    def f1(h):
        x = ApproCompteOp.objects.filter(household=h).aggregate(Sum('amount'))['amount__sum']
        return x if x else Decimal(0)
    def f2(h):
        x = PurchaseDetailOp.objects.filter(purchase__household=h).aggregate(Sum('price'))['price__sum']
        return x if x else Decimal(0)
    households = [{'name': h.pk, 'account': h.account,
                   'computed': f1(h) + f2(h) } for h in Household.objects.all()]
    return render(request, 'base/database_info.html', {'pdts': pdts, 'households': households,})
