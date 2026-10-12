"""Labelled non-English replies for the rule-1 classifier (used by scripts/eval_classifier.py --set multilingual).

The same 12 hard cases in Italian, Spanish, Portuguese, French and German: the languages seen in the
2026-10-07 backtest (Italian and Spanish were 20 of 24 non-English replies), plus mixed-language
replies modelled on real ones. True = the reply asks the customer something (PENDING is right).
"""

# (label, case id) -> {language: reply}
BASE = {
    (True, "job id"): {
        "it": "Grazie per averci contattato. Per favore condividi il Job ID dell'app interessata, così possiamo verificare. Lo trovi nell'URL della pagina del progetto.",
        "es": "Gracias por escribirnos. Por favor, comparte el Job ID de la aplicación afectada para que podamos revisarlo. Lo encontrarás en la URL de la página del proyecto.",
        "pt": "Obrigado pelo contato. Por favor, compartilhe o Job ID do app afetado para que possamos verificar. Você encontra no URL da página do projeto.",
        "fr": "Merci de nous avoir contactés. Merci de nous indiquer le Job ID de l'application concernée afin que nous puissions vérifier. Vous le trouverez dans l'URL de la page du projet.",
        "de": "Danke für Ihre Nachricht. Bitte teilen Sie uns die Job-ID der betroffenen App mit, damit wir das prüfen können. Sie finden sie in der URL der Projektseite.",
    },
    (True, "restore target"): {
        "it": "Abbiamo pronto il backup di ieri. Prima di ripristinarlo, conferma se deve andare sull'app di produzione o sull'ambiente di anteprima, perché il ripristino sovrascrive i dati attuali.",
        "es": "Ya tenemos listo el backup de ayer. Antes de restaurarlo, confirma si debe ir a la app de producción o al entorno de vista previa, porque la restauración sobrescribe los datos actuales.",
        "pt": "Já temos o backup de ontem pronto. Antes de restaurar, confirme se ele deve ir para o app de produção ou para o ambiente de preview, porque a restauração substitui os dados atuais.",
        "fr": "La sauvegarde d'hier est prête. Avant de la restaurer, confirmez-nous si elle doit aller sur l'application de production ou sur l'environnement de prévisualisation, car la restauration écrase les données actuelles.",
        "de": "Das Backup von gestern ist bereit. Bevor wir es wiederherstellen, bestätigen Sie bitte, ob es in die Produktions-App oder in die Vorschau-Umgebung soll, da die Wiederherstellung die aktuellen Daten überschreibt.",
    },
    (True, "try and report"): {
        "it": "Sembra una versione in cache del sito. Puoi provare a svuotare la cache del browser e aprire l'app in una finestra privata, e poi dirci se vedi ancora la vecchia versione?",
        "es": "Parece una versión en caché del sitio. ¿Puedes borrar la caché del navegador y abrir la app en una ventana privada, y luego decirnos si sigues viendo la versión antigua?",
        "pt": "Parece uma versão em cache do site. Você pode limpar o cache do navegador e abrir o app numa janela anônima, e depois nos dizer se ainda vê a versão antiga?",
        "fr": "Il semble s'agir d'une version en cache du site. Pouvez-vous vider le cache du navigateur, ouvrir l'application en navigation privée, puis nous dire si vous voyez toujours l'ancienne version ?",
        "de": "Das sieht nach einer zwischengespeicherten Version der Seite aus. Können Sie den Browser-Cache leeren, die App in einem privaten Fenster öffnen und uns dann sagen, ob Sie noch die alte Version sehen?",
    },
    (True, "which email"): {
        "it": "Non troviamo un abbonamento attivo con questo indirizzo email. Con quale indirizzo email ti sei abbonato? Potrebbe essere diverso da quello da cui ci scrivi.",
        "es": "No encontramos una suscripción activa con este correo. ¿Con qué correo te suscribiste? Puede que sea distinto del que usas para escribirnos.",
        "pt": "Não encontramos uma assinatura ativa com este e-mail. Com qual e-mail você assinou? Pode ser diferente do que está usando para nos escrever.",
        "fr": "Nous ne trouvons pas d'abonnement actif avec cette adresse e-mail. Avec quelle adresse vous êtes-vous abonné ? Elle est peut-être différente de celle que vous utilisez pour nous écrire.",
        "de": "Wir finden kein aktives Abonnement unter dieser E-Mail-Adresse. Mit welcher E-Mail-Adresse haben Sie das Abo abgeschlossen? Es könnte eine andere sein als die, von der Sie schreiben.",
    },
    (True, "offer needs yes"): {
        "it": "Possiamo trasferire la proprietà dell'app all'account del tuo collega. Vuoi che procediamo con il trasferimento a jordan@acme.io? Rispondi sì e lo facciamo subito.",
        "es": "Podemos transferir la propiedad de la app a la cuenta de tu compañero. ¿Quieres que hagamos la transferencia a jordan@acme.io? Responde sí y lo hacemos enseguida.",
        "pt": "Podemos transferir a propriedade do app para a conta do seu colega. Quer que façamos a transferência para jordan@acme.io? Responda sim e fazemos na hora.",
        "fr": "Nous pouvons transférer la propriété de l'application vers le compte de votre collègue. Voulez-vous que nous procédions au transfert vers jordan@acme.io ? Répondez oui et nous le faisons tout de suite.",
        "de": "Wir können die App in das Konto Ihres Kollegen übertragen. Sollen wir die Übertragung an jordan@acme.io durchführen? Antworten Sie einfach mit Ja, dann erledigen wir das sofort.",
    },
    (True, "buried ask"): {
        "it": "Grazie per i dettagli. Abbiamo controllato la configurazione email della tua app e il dominio di invio è configurato correttamente. Per capire meglio, potresti inviarci un indirizzo che non ha ricevuto l'email e l'orario approssimativo di invio? Nel frattempo, ecco come funziona la consegna: i messaggi passano dal nostro provider, che riprova per 24 ore, e i filtri antispam del destinatario possono trattenere i messaggi. Cordiali saluti, il team di supporto Emergent",
        "es": "Gracias por los detalles. Revisamos la configuración de correo de tu app y el dominio de envío está bien configurado. Para acotar el problema, ¿podrías enviarnos una dirección que no recibió el correo y la hora aproximada del envío? Mientras tanto, así funciona la entrega: los mensajes salen por nuestro proveedor, que reintenta durante 24 horas, y los filtros de spam del destinatario pueden retenerlos. Un saludo, el equipo de soporte de Emergent",
        "pt": "Obrigado pelos detalhes. Verificamos a configuração de e-mail do seu app e o domínio de envio está correto. Para entender melhor, você poderia nos enviar um endereço que não recebeu o e-mail e o horário aproximado do envio? Enquanto isso, veja como funciona a entrega: as mensagens saem pelo nosso provedor, que tenta novamente por 24 horas, e os filtros de spam do destinatário podem retê-las. Atenciosamente, equipe de suporte Emergent",
        "fr": "Merci pour ces détails. Nous avons vérifié la configuration e-mail de votre application et le domaine d'envoi est correctement configuré. Pour affiner, pourriez-vous nous envoyer une adresse qui n'a pas reçu l'e-mail et l'heure approximative d'envoi ? En attendant, voici comment fonctionne la livraison : les messages passent par notre fournisseur, qui réessaie pendant 24 heures, et les filtres anti-spam du destinataire peuvent les retenir. Cordialement, l'équipe support Emergent",
        "de": "Danke für die Details. Wir haben die E-Mail-Einrichtung Ihrer App geprüft, die Absenderdomain ist korrekt konfiguriert. Um das einzugrenzen: Könnten Sie uns eine Adresse schicken, die keine E-Mail erhalten hat, und ungefähr die Uhrzeit des Versands? Zur Erklärung: Nachrichten laufen über unseren Anbieter, der 24 Stunden lang erneut zustellt, und Spamfilter beim Empfänger können sie zurückhalten. Viele Grüße, Ihr Emergent-Support-Team",
    },
    (False, "courtesy question"): {
        "it": "Abbiamo aggiunto i 50 crediti mancanti al tuo account e ora sono visibili nella dashboard. C'è altro con cui posso aiutarti oggi?",
        "es": "Hemos añadido los 50 créditos que faltaban a tu cuenta y ya aparecen en el panel. ¿Hay algo más en lo que pueda ayudarte hoy?",
        "pt": "Adicionamos os 50 créditos que faltavam na sua conta e eles já aparecem no painel. Posso ajudar em mais alguma coisa hoje?",
        "fr": "Nous avons ajouté les 50 crédits manquants à votre compte, ils sont maintenant visibles dans le tableau de bord. Puis-je vous aider pour autre chose aujourd'hui ?",
        "de": "Wir haben die fehlenden 50 Credits Ihrem Konto gutgeschrieben, sie sind jetzt im Dashboard sichtbar. Kann ich Ihnen heute sonst noch irgendwie helfen?",
    },
    (False, "rhetorical"): {
        "it": "Perché la build falliva? Nei requisiti del backend c'era un pacchetto inesistente, lintiq==0.1.3, quindi ogni installazione si fermava lì. Abbiamo rimosso quella riga e ripubblicato: l'app è di nuovo online sul tuo dominio.",
        "es": "¿Por qué fallaba la build? En los requisitos del backend había un paquete que no existe, lintiq==0.1.3, así que cada instalación se detenía ahí. Quitamos esa línea y volvimos a publicar: la app ya está en línea en tu dominio.",
        "pt": "Por que o build falhava? Nos requisitos do backend havia um pacote inexistente, lintiq==0.1.3, então toda instalação parava ali. Removemos essa linha e publicamos de novo: o app já está no ar no seu domínio.",
        "fr": "Pourquoi le build échouait-il ? Les dépendances du backend contenaient un paquet inexistant, lintiq==0.1.3, donc chaque installation s'arrêtait là. Nous avons supprimé cette ligne et republié : l'application est de nouveau en ligne sur votre domaine.",
        "de": "Warum ist der Build fehlgeschlagen? In den Backend-Abhängigkeiten stand ein Paket, das es nicht gibt, lintiq==0.1.3, daher brach jede Installation dort ab. Wir haben die Zeile entfernt und neu veröffentlicht: Die App ist wieder unter Ihrer Domain online.",
    },
    (False, "we will update"): {
        "it": "Abbiamo inoltrato il problema al nostro team di ingegneria, che ci sta già lavorando. Ti aggiorneremo su questo ticket entro 48 ore. Nel frattempo non è necessaria nessuna azione da parte tua.",
        "es": "Hemos escalado el problema a nuestro equipo de ingeniería, que ya está trabajando en ello. Te daremos novedades en este ticket en un plazo de 48 horas. Mientras tanto, no necesitas hacer nada.",
        "pt": "Encaminhamos o problema para a nossa equipe de engenharia, que já está trabalhando nisso. Vamos atualizar você neste ticket em até 48 horas. Enquanto isso, nenhuma ação é necessária da sua parte.",
        "fr": "Nous avons transmis le problème à notre équipe d'ingénierie, qui y travaille déjà. Nous vous tiendrons informé sur ce ticket sous 48 heures. D'ici là, aucune action n'est nécessaire de votre part.",
        "de": "Wir haben das Problem an unser Engineering-Team weitergegeben, das bereits daran arbeitet. Wir melden uns innerhalb von 48 Stunden in diesem Ticket. Bis dahin müssen Sie nichts tun.",
    },
    (False, "generic conditional"): {
        "it": "Abbiamo corretto il percorso del Dockerfile che bloccava la build e abbiamo ripubblicato. L'app è di nuovo online. Se il problema dovesse ripresentarsi dopo il prossimo deploy, sentiti libero di rispondere qui.",
        "es": "Corregimos la ruta del Dockerfile que rompía la build y volvimos a desplegar. La app ya está en línea. Si el problema vuelve a aparecer después de tu próximo despliegue, no dudes en responder aquí.",
        "pt": "Corrigimos o caminho do Dockerfile que quebrava o build e publicamos de novo. O app está no ar novamente. Se o problema voltar depois do seu próximo deploy, fique à vontade para responder aqui.",
        "fr": "Nous avons corrigé le chemin du Dockerfile qui cassait le build et redéployé. L'application est de nouveau en ligne. Si le problème réapparaît après votre prochain déploiement, n'hésitez pas à répondre ici.",
        "de": "Wir haben den Dockerfile-Pfad korrigiert, der den Build verhindert hat, und neu bereitgestellt. Die App ist wieder online. Falls das Problem nach Ihrem nächsten Deployment wieder auftritt, antworten Sie gerne hier.",
    },
    (False, "quoted question"): {
        "it": "Ci hai chiesto se puoi ottenere un rimborso per l'esecuzione fallita. Sì: abbiamo riaccreditato i 20 crediti di quell'esecuzione sul tuo saldo, e trovi la rettifica nella cronologia di fatturazione.",
        "es": "Nos preguntaste si podías recibir un reembolso por la ejecución fallida. Sí: hemos devuelto a tu saldo los 20 créditos de esa ejecución y puedes ver el ajuste en tu historial de facturación.",
        "pt": "Você perguntou se poderia receber um reembolso pela execução que falhou. Sim: devolvemos ao seu saldo os 20 créditos dessa execução, e o ajuste aparece no seu histórico de cobrança.",
        "fr": "Vous nous avez demandé si vous pouviez être remboursé pour l'exécution qui a échoué. Oui : nous avons recrédité les 20 crédits de cette exécution sur votre solde, et l'ajustement figure dans votre historique de facturation.",
        "de": "Sie haben gefragt, ob Sie für den fehlgeschlagenen Lauf eine Erstattung bekommen können. Ja: Wir haben die 20 Credits dieses Laufs Ihrem Guthaben gutgeschrieben, die Korrektur sehen Sie in Ihrem Abrechnungsverlauf.",
    },
    (False, "we will send"): {
        "it": "Grazie per il messaggio. Il file di esportazione è in preparazione e te lo invieremo qui su questo ticket. Se nel frattempo hai bisogno di altro, rispondi pure qui.",
        "es": "Gracias por tu mensaje. El archivo de exportación se está preparando y te lo enviaremos aquí, en este ticket. Si mientras tanto necesitas algo más, responde aquí.",
        "pt": "Obrigado pela mensagem. O arquivo de exportação está sendo preparado e vamos enviá-lo aqui neste ticket. Se precisar de mais alguma coisa enquanto isso, é só responder aqui.",
        "fr": "Merci pour votre message. Le fichier d'export est en cours de préparation et nous vous l'enverrons ici, sur ce ticket. Si vous avez besoin d'autre chose entre-temps, répondez simplement ici.",
        "de": "Danke für Ihre Nachricht. Die Exportdatei wird gerade vorbereitet, wir schicken sie Ihnen hier in diesem Ticket. Wenn Sie in der Zwischenzeit noch etwas brauchen, antworten Sie einfach hier.",
    },
}

# Modelled on real replies from the backtest: Italian/Spanish emails that embed an English prompt for the
# customer's agent, and the two Italian asks that were wrongly flagged on 2026-10-07.
EXTRA = [
    (True, "it", "real: which step next",
     "Ecco il riepilogo dei punti che restano: 1. Area lezioni e quiz. 2. Sezione promo. 3. Feed live. "
     "Da non fare: il collegamento diretto a Betfair. Dimmi da quale punto vuoi ripartire e ti do il prompt. "
     "Cordiali saluti, Team di supporto Emergent"),
    (True, "it", "real: ownership proof",
     "Non posso controllare i crediti perché il progetto titans-odds non risulta collegato a questa email. "
     "Per controllarli mi serve la conferma di proprietà: se il progetto è sotto un altro tuo account, scrivici da "
     "quell'email oppure mandami il link con il nome del progetto. Cordiali saluti, Team di supporto Emergent"),
    (False, "es", "mixed: English prompt, nothing asked",
     "Hola Francisco, ya revisamos tu app. Copia y pega este mensaje en el chat del agente: "
     "\"Add automatic renewal to the subscription flow, handle cancellations through the existing webhook, "
     "and don't create a second Stripe integration. Test in preview first.\" Con eso queda resuelto. "
     "Un saludo, el equipo de soporte de Emergent"),
    (True, "es", "mixed: English prompt, then an ask",
     "Hola Francisco, ya revisamos tu app. Copia y pega este mensaje en el chat del agente: "
     "\"Add automatic renewal to the subscription flow and handle cancellations through the existing webhook.\" "
     "Cuando el agente termine, ¿nos puedes enviar una captura de la pantalla de suscripción para confirmar que "
     "todo funciona? Un saludo, el equipo de soporte de Emergent"),
]

LANG_NAMES = {"it": "Italian", "es": "Spanish", "pt": "Portuguese", "fr": "French", "de": "German"}

CASES = [
    (label, f"[{lang}] {case}", "", reply)
    for (label, case), by_lang in BASE.items()
    for lang, reply in by_lang.items()
] + [(label, f"[{lang}] {case}", "", reply) for label, lang, case, reply in EXTRA]
