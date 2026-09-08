# Portafoglio: credito, ricariche, giroconto, cassa

## Cosa permette di fare

Gestire il credito prepagato di ogni socio: come si ricarica, come si
trasferisce tra soci, e come il gruppo tiene traccia di ogni movimento
(cassa). È il cuore del modello "prepagato" di DDGAS — vedi
[`panoramica.md`](panoramica.md) per l'idea generale.

Ogni socio versa una somma nel conto corrente del GAS; quell'importo
diventa credito sul sito. Quando partecipa a un ordine, il costo viene
scalato automaticamente dal credito alla chiusura dell'ordine: non
serve mai gestire contanti al momento del ritiro.

## Chi la può usare

- Ogni socio vede il proprio credito e i propri movimenti, e può
  ricaricare o fare un giroconto verso un altro socio.
- Il moderatore/tesoriere vede la cassa complessiva, tutti i movimenti di
  tutti i soci, e gestisce riconciliazione pagamenti, rettifiche ed
  eliminazione di movimenti errati.

## Prerequisiti

- Un conto corrente dedicato al gruppo con IBAN comunicato ai soci
  (necessario per i bonifici, sempre disponibili).
- Opzionale: un account Stripe e/o Satispay attivo, per abilitare anche
  la ricarica con carta o app — senza, resta comunque disponibile la
  ricarica via bonifico.

## Come si usa

### Ricaricare il credito

Tre vie, a seconda di cosa è stato attivato per l'istanza:

1. **Carta (Stripe)** — se abilitato, il socio sceglie un importo e paga
   con carta tramite una pagina di checkout; il credito si aggiorna
   automaticamente a pagamento confermato.
2. **Satispay** — stesso principio, se il gruppo ha attivato anche
   questo metodo.
3. **Bonifico** — sempre disponibile. Il socio fa un bonifico verso
   l'IBAN del gruppo e, sul sito, dichiara l'importo versato prima o dopo
   averlo fatto: quando lo staff carica l'estratto conto, il sito
   riconosce automaticamente il bonifico che corrisponde all'importo
   dichiarato (o, in mancanza di dichiarazione, cerca username, nome e
   cognome, email o codice personale nella causale del bonifico) e
   accredita da solo. Solo i bonifici che restano ambigui (o senza alcun
   riferimento riconoscibile) finiscono in una coda che lo staff risolve
   a mano.

### Giroconto

Un socio può trasferire parte del proprio credito a un altro socio
direttamente dal sito — utile per saldare piccole somme tra soci senza
passare dal conto corrente.

### Cassa e movimenti

Ogni operazione che tocca il credito (ricarica, ordine, rettifica,
giroconto, tesseramento) genera un movimento tracciato, visibile al
socio per il proprio storico e al moderatore/tesoriere per la cassa
complessiva del gruppo — inclusa la possibilità di esportare tutto in
CSV.
