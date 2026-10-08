# Proposta: ottimizzazione portabile dello stack AI
Stato: approvato il 2026-10-08.

## Obiettivo
Evolvere il setup esistente in un progetto pubblico per Codex e Claude Code. Applicarlo prima al sistema personale, poi pubblicare il pacchetto generico senza percorsi o dati personali. CLI Python come motore, skill /setup come ingresso guidato.

## Approcci
1. Consigliato: evolvere ai-config con moduli e adattatori per agente. Riusa il setup esistente, mantiene poche dipendenze, richiede controlli di compatibilità.
2. Fork di claude-reimagined: bootstrap già disponibile ma centrato su Claude, con molte componenti non necessarie al workflow personale.
3. Installare ECC completo: copertura ampia ma carico maggiore e impostazioni da adattare alle regole personali.

## Prima versione
- Audit locale: agenti e versioni, hook registrati, dipendenze, skill duplicate, dimensione delle istruzioni. Le stime di token vanno etichettate come stime; non equivalgono al contesto realmente caricato.
- Setup modulare: PDF testo, handoff, regole concise, monitoraggio; conservare configurazioni di altri strumenti.
- Contesto: soglie di avviso e handoff personalizzabili in percentuale oppure token, con modalità solo avviso o handoff a fine turno. Conservare 30/35% nel profilo personale finché non viene scelto altro. Mostrare finestra del modello rilevata; se sconosciuta chiedere il valore o dichiarare misura non disponibile. Una soglia configurata non amplia né impone un limite hardware alla finestra del modello. Non cambiare modello/effort automaticamente.
- Output grandi: integrazione RTK facoltativa, inizialmente su comandi selezionati, con percorso per recuperare output integrale e verifica di errori/exit code. Nessuna riscrittura globale finché non validata.
- Indicizzazione: mantenere graphify dove già usato; context-mode e code-review-graph come integrazioni opzionali solo dopo audit delle sovrapposizioni.
- Report prima/dopo per Claude e Codex: input, cache, output, tempi e successo del task. Non equiparare costo relativo e fattura né sommare risparmi percentuali dichiarati da strumenti diversi.
- Installazione: anteprima, backup con identificativo univoco, manifest dei file gestiti, check, rollback che rileva modifiche successive prima di ripristinare. Supporto Mac/Linux, test simulati Windows con limite dichiarato finché non provato realmente.
- Test: idempotenza, configurazioni preesistenti, backup/rollback, soglie e finestra sconosciuta, parser Claude/Codex su fixture prive di dati privati; test delle integrazioni opzionali separati.

## Correzioni individuate nel codice attuale
handoff_guard.py assume 1M per Claude non-Haiku e contiene una frase non dimostrata su costi/qualità oltre soglia. measure_tokens.py copre solo Claude e usa pesi convenzionali. install.py copia handoff in due directory lette da Codex; backup datato può sovrascrivere backup dello stesso giorno. README contiene indicazioni contraddittorie sugli hook Codex. --check verifica registrazione, non esecuzione o approvazione.

## Fonti e riuso
https://github.com/kunaltulsidasani/claude-reimagined (bootstrap modulare e verifica)
https://github.com/affaan-m/ECC (budget del contesto e adattatori multi-agente)
https://github.com/rtk-ai/rtk (filtri output e passthrough)
https://github.com/mksglu/context-mode (indicizzazione e recupero mirato; dipendenza opzionale con propria licenza ELv2)
Verificare licenza e attribuzione di ogni file prima di copiarlo; preferire dipendenze versionate e implementazione propria dei moduli di orchestrazione.

## Fuori dalla prima versione
DeepGEMM, Caveman, installazione indiscriminata di skill, routing automatico del modello principale, interfaccia grafica. Nome iniziale: agent-stack-optimizer.

## Sequenza
Approvare questa proposta; implementare e verificare il core in ambiente temporaneo; applicarlo al sistema personale con backup; misurare; preparare e pubblicare il pacchetto pubblico autorizzato dall’utente.
