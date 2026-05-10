# ── AWS Connect instance ──────────────────────────────────────────────────────

resource "aws_connect_instance" "demo" {
  instance_alias                   = var.instance_alias
  identity_management_type         = "CONNECT_MANAGED"
  inbound_calls_enabled            = false
  outbound_calls_enabled           = true
  contact_flow_logs_enabled        = true
  contact_lens_enabled             = true
  auto_resolve_best_voices_enabled = true
  early_media_enabled              = true

  timeouts {
    create = "15m"
    delete = "15m"
  }
}

# ── Phone number for outbound calls ──────────────────────────────────────────

resource "aws_connect_phone_number" "demo" {
  target_arn   = aws_connect_instance.demo.arn
  country_code = var.phone_country_code
  type         = "DID"
  description  = "CMP Voice Demo - numéro source sortant"

  timeouts {
    create = "5m"
  }
}

# ── Outbound contact flow ─────────────────────────────────────────────────────
#
# Scénario : CMP appelle l'entrepôt Intermarché pour confirmer la livraison
# du 15 mai (48 cartons LED Pro 100W). L'agent parle en Léa (fr-FR) avec des
# pauses SSML <break> pour laisser le réceptionniste répondre. Contact Lens
# transcrit la totalité de l'échange pour l'analyse post-appel.
#
# Formats validés via CLI :
#   - UpdateContactTextToSpeechVoice  (TextToSpeechVoice = "Lea")
#   - MessageParticipant              (SSML = "<speak>...</speak>")
#   - DisconnectParticipant
# GetParticipantInput n'est pas un type valide dans cette version d'API ;
# les pauses utilisent <break time='Xs'/> dans le SSML.

locals {
  ssml_greet = "<speak>Bonjour, ici C.M.P., votre distributeur. Je vous appelle concernant votre livraison prévue le quinze mai. Êtes-vous disponible pour confirmer les détails ? <break time='8s'/></speak>"

  ssml_confirm_receipt = "<speak>Merci. Vous devez recevoir quarante-huit cartons d'Éclairage LED Pro cent watts, quai numéro trois. Pouvez-vous confirmer la réception ? <break time='8s'/></speak>"

  ssml_confirm_dock = "<speak>Très bien. La livraison nécessite un camion avec hayon. Disposez-vous d'un quai équipé disponible ce jour-là ? <break time='8s'/></speak>"

  ssml_confirm_time = "<speak>Parfait. Avez-vous une préférence pour l'heure, plutôt neuf heures ou onze heures ? <break time='8s'/></speak>"

  ssml_close = "<speak>Noté. La livraison est donc confirmée pour le quinze mai matin, quai numéro trois, à votre entrepôt de Saint-Brieuc. Nous vous enverrons un récapitulatif par courriel. Merci et excellente journée !</speak>"
}

resource "aws_connect_contact_flow" "outbound_demo" {
  instance_id = aws_connect_instance.demo.id
  name        = "CMP Confirmation Livraison"
  description = "Appel sortant de confirmation de livraison - scénario demo"
  type        = "CONTACT_FLOW"

  content = jsonencode({
    Version     = "2019-10-30"
    StartAction = "set-voice"
    Actions = [
      {
        Identifier = "set-voice"
        Type       = "UpdateContactTextToSpeechVoice"
        Parameters = { TextToSpeechVoice = "Lea" }
        Transitions = { NextAction = "greet", Errors = [], Conditions = [] }
      },
      {
        Identifier = "greet"
        Type       = "MessageParticipant"
        Parameters = { SSML = local.ssml_greet }
        Transitions = { NextAction = "confirm-receipt", Errors = [], Conditions = [] }
      },
      {
        Identifier = "confirm-receipt"
        Type       = "MessageParticipant"
        Parameters = { SSML = local.ssml_confirm_receipt }
        Transitions = { NextAction = "confirm-dock", Errors = [], Conditions = [] }
      },
      {
        Identifier = "confirm-dock"
        Type       = "MessageParticipant"
        Parameters = { SSML = local.ssml_confirm_dock }
        Transitions = { NextAction = "confirm-time", Errors = [], Conditions = [] }
      },
      {
        Identifier = "confirm-time"
        Type       = "MessageParticipant"
        Parameters = { SSML = local.ssml_confirm_time }
        Transitions = { NextAction = "close", Errors = [], Conditions = [] }
      },
      {
        Identifier = "close"
        Type       = "MessageParticipant"
        Parameters = { SSML = local.ssml_close }
        Transitions = { NextAction = "end", Errors = [], Conditions = [] }
      },
      {
        Identifier  = "end"
        Type        = "DisconnectParticipant"
        Parameters  = {}
        Transitions = {}
      }
    ]
  })
}
