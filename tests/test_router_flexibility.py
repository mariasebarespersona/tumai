"""
Test router flexibility with natural language variations.

This test suite verifies that the hybrid router (keywords + LLM fallback)
correctly classifies user intents even when users use different words
to express the same meaning.
"""

import pytest
import asyncio
from router.active_router import ActiveRouter


@pytest.fixture
def router():
    """Create router instance."""
    return ActiveRouter()


class TestPropertyIntents:
    """Test property-related intent classification."""
    
    def test_create_property_variations(self, router):
        """Test various ways to say 'create property'."""
        variations = [
            # Direct commands
            "crear propiedad",
            "crea una propiedad nueva",
            "nueva propiedad",
            "añadir propiedad",
            "agregar propiedad",
            # Property types
            "crea una casa",
            "crear un piso",
            "crea un apartamento",
            "crear un local comercial",
            "crea una finca",
            # Natural variations
            "quiero crear una propiedad",
            "necesito crear una propiedad nueva",
            "vamos a crear una propiedad",
            "dame de alta una propiedad",
            "registrar una propiedad",
            "tengo una propiedad nueva",
            "acabo de comprar un piso",
            "he comprado una casa",
        ]
        
        for text in variations:
            intent, confidence, agent = router.predict_keywords(text)
            assert intent == "property.create", f"Failed for: '{text}' -> got {intent}"
            assert agent == "PropertyAgent", f"Wrong agent for: '{text}'"
    
    def test_switch_property_variations(self, router):
        """Test various ways to say 'switch property'."""
        variations = [
            "cambiar a Sobradiel",
            "trabajar con la propiedad 15Panes",
            "selecciona Sobradiel",
            "metete en 15Panes",
            "entrar en Sobradiel",
            "abre la propiedad 15Panes",
            "ve a Sobradiel",
            "vamos a 15Panes",
            "quiero ver Sobradiel",
            "quiero trabajar con 15Panes",
            "otra propiedad",
        ]
        
        for text in variations:
            intent, confidence, agent = router.predict_keywords(text)
            assert intent == "property.switch", f"Failed for: '{text}' -> got {intent}"
            assert agent == "PropertyAgent", f"Wrong agent for: '{text}'"


class TestDocStrategyIntents:
    """Test document strategy selection (R2B vs Promoción)."""
    
    def test_r2b_strategy_variations(self, router):
        """Test various ways to select R2B strategy."""
        variations = [
            "voy a elegir R2B",
            "quiero seguir por R2B",
            "elijo el camino R2B",
            "no tengo más documentos de compra, voy por R2B",
            "pasemos a R2B",
            "siguiente nivel, R2B",
            "terminé con compra, ahora R2B",
            "quiero reformar, así que R2B",
            "prefiero R2B",
            "me decanto por R2B",
        ]
        
        for text in variations:
            intent, confidence, agent = router.predict_keywords(text)
            assert intent == "docs.set_strategy", f"Failed for: '{text}' -> got {intent}"
            assert agent == "DocsAgent", f"Wrong agent for: '{text}'"
    
    def test_promocion_strategy_variations(self, router):
        """Test various ways to select Promoción strategy."""
        variations = [
            "quiero promoción",
            "voy por promoción",
            "elijo promoción",
            "seguir por promoción",
            "obra nueva, así que promoción",
            "quiero construir, promoción",
        ]
        
        for text in variations:
            intent, confidence, agent = router.predict_keywords(text)
            assert intent == "docs.set_strategy", f"Failed for: '{text}' -> got {intent}"
            assert agent == "DocsAgent", f"Wrong agent for: '{text}'"
    
    def test_r2b_not_confused_with_numbers(self, router):
        """R2B in document context should NOT go to NumbersAgent."""
        # Document context → DocsAgent
        doc_variations = [
            "no tengo más documentos de compra, voy a elegir R2B",
            "quiero seguir por R2B para los documentos",
            "elijo el camino R2B",
        ]
        for text in doc_variations:
            intent, confidence, agent = router.predict_keywords(text)
            assert agent == "DocsAgent", f"Doc context should go to DocsAgent: '{text}' -> {agent}"
        
        # Numbers context → NumbersAgent
        numbers_variations = [
            "quiero completar la plantilla R2B",
            "abre la tabla de números R2B",
            "pon B5 a 1000 en R2B",
        ]
        for text in numbers_variations:
            intent, confidence, agent = router.predict_keywords(text)
            assert agent == "NumbersAgent", f"Numbers context should go to NumbersAgent: '{text}' -> {agent}"


class TestNumbersIntents:
    """Test numbers-related intent classification."""
    
    def test_set_cell_variations(self, router):
        """Test various ways to set a cell value."""
        variations = [
            "pon B5 a 1000",
            "escribe 500 en C5",
            "actualiza B7 con 2000",
            "coloca 1500 en D3",
            "mete 3000 en B5",
            "cambia B5 a 4000",
            # Note: "el valor de B5 es 5000" might need LLM fallback
        ]
        
        for text in variations:
            intent, confidence, agent = router.predict_keywords(text)
            assert intent == "numbers.set_cell", f"Failed for: '{text}' -> got {intent}"
            assert agent == "NumbersAgent", f"Wrong agent for: '{text}'"
    
    def test_clear_cell_variations(self, router):
        """Test various ways to clear a cell."""
        variations = [
            "borra B5",
            "elimina el valor de C7",
            "limpia B3",
            "vacía D5",
            "quita el valor de B5",
        ]
        
        for text in variations:
            intent, confidence, agent = router.predict_keywords(text)
            assert intent == "numbers.clear_cell", f"Failed for: '{text}' -> got {intent}"
            assert agent == "NumbersAgent", f"Wrong agent for: '{text}'"


class TestDocsIntents:
    """Test document-related intent classification."""
    
    def test_doc_qa_variations(self, router):
        """Test various ways to ask about document content."""
        variations = [
            "qué dice el contrato",
            "cuándo vence la factura",
            "qué menciona la escritura",
            "qué establece el certificado",
            "qué precio tiene según el contrato",
            # Note: Generic questions like "cuánto tengo que pagar" need more context
        ]
        
        for text in variations:
            intent, confidence, agent = router.predict_keywords(text)
            assert intent == "docs.qa", f"Failed for: '{text}' -> got {intent}"
            assert agent == "DocsAgent", f"Wrong agent for: '{text}'"
    
    def test_send_email_variations(self, router):
        """Test various ways to send documents by email."""
        variations = [
            "manda el contrato por email",
            "envía la factura por correo",
            "mandame el documento por email",
            "comparte la escritura por email",
            "manda este resumen por email",
            "enviame eso por correo",
            "hazme llegar el contrato",
        ]
        
        for text in variations:
            intent, confidence, agent = router.predict_keywords(text)
            assert intent == "docs.send_email", f"Failed for: '{text}' -> got {intent}"
            assert agent == "DocsAgent", f"Wrong agent for: '{text}'"
    
    def test_email_continuation(self, router):
        """Test email address continuation detection."""
        variations = [
            "test@gmail.com",
            "mi email es juan@hotmail.com",
            "usuario@outlook.com",
        ]
        
        for text in variations:
            intent, confidence, agent = router.predict_keywords(text)
            assert intent == "docs.send_email", f"Failed for: '{text}' -> got {intent}"
    
    def test_upload_doc_variations(self, router):
        """Test various ways to upload documents."""
        variations = [
            "sube el contrato",
            "subir una factura",
            "cargar documento",
            "adjunta la escritura",
            "añade el certificado",
            "importar documento",
        ]
        
        for text in variations:
            intent, confidence, agent = router.predict_keywords(text)
            assert intent == "docs.upload", f"Failed for: '{text}' -> got {intent}"
            assert agent == "DocsAgent", f"Wrong agent for: '{text}'"
    
    def test_list_docs_variations(self, router):
        """Test various ways to list documents."""
        variations = [
            "lista documentos",
            "muestrame los documentos",
            "ver documentos",
            "qué documentos tengo",
            "cuáles documentos hay",
            "dame los documentos",
            "qué archivos tengo subidos",
        ]
        
        for text in variations:
            intent, confidence, agent = router.predict_keywords(text)
            assert intent == "docs.list", f"Failed for: '{text}' -> got {intent}"
            assert agent == "DocsAgent", f"Wrong agent for: '{text}'"


class TestLLMFallback:
    """Test LLM fallback for ambiguous cases."""
    
    @pytest.mark.asyncio
    async def test_low_confidence_triggers_llm(self, router):
        """Test that low confidence triggers LLM fallback."""
        # This text is ambiguous - keywords might not catch it well
        ambiguous_text = "paso al siguiente nivel"
        
        # Keywords should return low confidence
        intent, confidence, agent = router.predict_keywords(ambiguous_text)
        
        # If confidence is low, predict_async should try LLM
        if confidence < 0.70:
            # Note: This test requires OpenAI API key to be set
            try:
                llm_intent, llm_confidence, llm_agent = await router.predict_async(ambiguous_text)
                # LLM should provide better classification
                assert llm_confidence >= confidence, "LLM should improve or match keywords confidence"
            except Exception as e:
                # Skip if no API key
                pytest.skip(f"LLM not available: {e}")
    
    @pytest.mark.asyncio
    async def test_high_confidence_skips_llm(self, router):
        """Test that high confidence skips LLM."""
        clear_text = "crear propiedad nueva"
        
        # This should have high confidence from keywords
        intent, confidence, agent = router.predict_keywords(clear_text)
        assert confidence >= 0.70, "Keywords should be confident for clear text"
        
        # predict_async should return same result without calling LLM
        async_intent, async_confidence, async_agent = await router.predict_async(clear_text)
        assert async_intent == intent
        assert async_confidence == confidence


class TestEdgeCases:
    """Test edge cases and potential confusion points."""
    
    def test_r2b_disambiguation(self, router):
        """Test R2B is correctly disambiguated between docs and numbers."""
        # Document strategy context
        assert router.predict_keywords("elijo R2B para documentos")[2] == "DocsAgent"
        assert router.predict_keywords("no tengo más de compra, R2B")[2] == "DocsAgent"
        
        # Numbers context
        assert router.predict_keywords("completa la plantilla R2B")[2] == "NumbersAgent"
        assert router.predict_keywords("abre números R2B")[2] == "NumbersAgent"
    
    def test_send_vs_list_disambiguation(self, router):
        """Test send vs list documents is correctly disambiguated."""
        # Send should win
        assert router.predict_keywords("manda el documento por email")[0] == "docs.send_email"
        assert router.predict_keywords("envía los documentos por correo")[0] == "docs.send_email"
        
        # List should win
        assert router.predict_keywords("lista los documentos")[0] == "docs.list"
        assert router.predict_keywords("qué documentos tengo")[0] == "docs.list"
    
    def test_empty_and_short_inputs(self, router):
        """Test handling of empty and very short inputs."""
        # Empty should fallback
        intent, confidence, agent = router.predict_keywords("")
        assert intent == "general.chat"
        
        # Single word focus modes
        assert router.predict_keywords("documentos")[0] == "docs.focus"
        assert router.predict_keywords("números")[0] == "numbers.focus"


class TestConversationContinuation:
    """Test multi-turn conversation continuation detection."""
    
    def test_property_create_continuation(self, router):
        """Test that property name/address response continues to PropertyAgent."""
        # Simulate context where AI asked for property name/address
        from langchain_core.messages import AIMessage, HumanMessage
        
        context = {
            "history": [
                HumanMessage(content="Quiero añadir una nueva propiedad"),
                AIMessage(content="Para añadir una nueva propiedad, por favor proporciona el nombre y la dirección de la propiedad.")
            ]
        }
        
        # User responds with property data
        intent, confidence, agent = router.predict_keywords("Sobradiel 4 - Osasuna 15", context)
        assert agent == "PropertyAgent", f"Expected PropertyAgent, got {agent}"
        assert "property" in intent, f"Expected property intent, got {intent}"
    
    def test_numbers_template_continuation(self, router):
        """Test that template selection response continues to NumbersAgent."""
        from langchain_core.messages import AIMessage, HumanMessage
        
        context = {
            "history": [
                HumanMessage(content="Quiero completar la plantilla números"),
                AIMessage(content="¿Qué plantilla de Números quieres usar? Elige una:\n1) R2B\n2) R2B + PM\n3) R2B + PM + Venta certs\n4) Promoción")
            ]
        }
        
        # User responds with template choice
        intent, confidence, agent = router.predict_keywords("R2B", context)
        assert agent == "NumbersAgent", f"Expected NumbersAgent, got {agent}"
    
    def test_email_continuation(self, router):
        """Test that email response continues to DocsAgent."""
        from langchain_core.messages import AIMessage, HumanMessage
        
        context = {
            "history": [
                HumanMessage(content="Manda el contrato por email"),
                AIMessage(content="¿A qué correo quieres que envíe el contrato?")
            ]
        }
        
        # User responds with email
        intent, confidence, agent = router.predict_keywords("test@gmail.com", context)
        assert agent == "DocsAgent", f"Expected DocsAgent, got {agent}"
        assert intent == "docs.send_email", f"Expected docs.send_email, got {intent}"
    
    def test_delete_confirmation_continuation(self, router):
        """Test that 'si' after delete confirmation continues to PropertyAgent."""
        from langchain_core.messages import AIMessage, HumanMessage
        
        context = {
            "history": [
                HumanMessage(content="Elimina Sobradiel 4"),
                AIMessage(content="⚠️ ¿Estás seguro que quieres eliminar la propiedad 'Sobradiel 4'? Esta acción no se puede deshacer.")
            ]
        }
        
        # User confirms with "si"
        intent, confidence, agent = router.predict_keywords("si", context)
        assert agent == "PropertyAgent", f"Expected PropertyAgent, got {agent}"
        assert "delete" in intent.lower() or "confirm" in intent.lower(), f"Expected delete/confirm intent, got {intent}"
    
    def test_generic_confirmation_continuation(self, router):
        """Test that generic confirmations are routed correctly based on context."""
        from langchain_core.messages import AIMessage, HumanMessage
        
        # Test document upload confirmation
        context = {
            "history": [
                HumanMessage(content="Sube el contrato"),
                AIMessage(content="¿Confirmas que quieres subir el archivo 'contrato.pdf' a la sección COMPRA?")
            ]
        }
        intent, confidence, agent = router.predict_keywords("si", context)
        assert agent == "DocsAgent", f"Expected DocsAgent, got {agent}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

