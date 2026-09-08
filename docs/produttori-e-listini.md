# Produttori e listini

## Cosa permette di fare

Tenere l'anagrafica dei fornitori del GAS (produttori) e, per ciascuno,
un listino di prodotti configurabile: prezzo, unità/quantità per collo,
quantità minima e massima ordinabile, colli disponibili, categoria e
note. Il listino è quello da cui i soci ordinano (vedi
[`ordini.md`](ordini.md)).

Ogni produttore ha anche uno storico degli ordini passati, consultabile
sia in generale sia per singolo socio.

## Chi la può usare

- Tutti i soci loggati vedono l'elenco produttori e i listini.
- Solo un **referente del produttore** (assegnato dal moderatore) o un
  **moderatore** possono creare/modificare un produttore, il suo listino,
  o disattivarlo.

## Prerequisiti

Nessuno oltre ad avere un ruolo abilitato: non serve altro per iniziare
ad aggiungere produttori.

## Come si usa

1. Il moderatore crea il produttore (nome, mesi in cui consegna, eventuale
   referente dedicato).
2. Il referente compila il listino prodotto per prodotto, oppure lo
   importa in blocco da un CSV — è disponibile un template scaricabile
   con le colonne attese, per evitare di doverle indovinare.
3. Il listino può essere aggiornato in qualsiasi momento (prezzi, nuovi
   prodotti, disponibilità); le modifiche valgono dal momento del
   salvataggio, non retroattivamente sugli ordini già chiusi.
4. Un produttore non più attivo si disattiva (non si cancella): resta
   visibile nello storico ordini, ma non compare più tra quelli su cui è
   possibile aprire un nuovo ordine.
