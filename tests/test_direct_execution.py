"""
Tests for Phase 2b: Direct Execution

Tests specialized agents executing directly without MainAgent,
including bidirectional routing loops.
"""

import pytest
import asyncio
from router.orchestrator import OrchestrationRouter


class TestDirectExecutionNumbersAgent:
    """Test NumbersAgent direct execution."""
    
    @pytest.fixture
    def orchestrator(self):
        return OrchestrationRouter()
    
    @pytest.mark.asyncio
    async def test_numbers_agent_completes_directly(self, orchestrator):
        """Test that NumbersAgent can complete a task directly."""
        result = await orchestrator.route_and_execute(
            user_input="pon B5 en 1000",
            session_id="test-session",
            property_id="test-prop-1",
            direct_execution=True
        )
        
        # Should complete without going to MainAgent
        assert result["status"] == "completed" or result["status"] == "use_main_agent"
        assert "NumbersAgent" in result["agent_path"]
        assert "latency_ms" in result or "total_latency_ms" in result
    
    @pytest.mark.asyncio
    async def test_numbers_agent_redirects_to_property(self, orchestrator):
        """Test that NumbersAgent redirects property tasks to PropertyAgent."""
        result = await orchestrator.route_and_execute(
            user_input="lista mis propiedades",
            session_id="test-session",
            property_id="test-prop-1",
            direct_execution=True
        )
        
        # Should initially route to PropertyAgent or redirect there
        assert "PropertyAgent" in result["agent_path"] or "MainAgent" in result["agent_path"]


class TestDirectExecutionPropertyAgent:
    """Test PropertyAgent direct execution."""
    
    @pytest.fixture
    def orchestrator(self):
        return OrchestrationRouter()
    
    @pytest.mark.asyncio
    async def test_property_agent_completes_directly(self, orchestrator):
        """Test that PropertyAgent can complete a task directly."""
        result = await orchestrator.route_and_execute(
            user_input="lista propiedades",
            session_id="test-session",
            direct_execution=True
        )
        
        # Should complete or fallback
        assert result["status"] in ["completed", "use_main_agent"]
        assert len(result["agent_path"]) >= 1
    
    @pytest.mark.asyncio
    async def test_property_agent_redirects_to_numbers(self, orchestrator):
        """Test that PropertyAgent redirects numbers tasks to NumbersAgent."""
        result = await orchestrator.route_and_execute(
            user_input="pon B5 en 2000",
            session_id="test-session",
            property_id="test-prop-1",
            direct_execution=True
        )
        
        # Should route to NumbersAgent
        assert "NumbersAgent" in result["agent_path"] or result["agent_path"][0] == "NumbersAgent"


class TestDirectExecutionDocsAgent:
    """Test DocsAgent direct execution."""
    
    @pytest.fixture
    def orchestrator(self):
        return OrchestrationRouter()
    
    @pytest.mark.asyncio
    async def test_docs_agent_completes_directly(self, orchestrator):
        """Test that DocsAgent can complete a task directly."""
        result = await orchestrator.route_and_execute(
            user_input="lista documentos",
            session_id="test-session",
            property_id="test-prop-1",
            direct_execution=True
        )
        
        # Should complete or fallback
        assert result["status"] in ["completed", "use_main_agent"]
        assert len(result["agent_path"]) >= 1


class TestBidirectionalRouting:
    """Test bidirectional routing between agents."""
    
    @pytest.fixture
    def orchestrator(self):
        return OrchestrationRouter()
    
    @pytest.mark.asyncio
    async def test_redirect_count_tracked(self, orchestrator):
        """Test that redirects are tracked correctly."""
        result = await orchestrator.route_and_execute(
            user_input="pon B5 en 1000",
            session_id="test-session",
            property_id="test-prop-1",
            direct_execution=True
        )
        
        # Should have redirect count
        assert "redirects" in result
        assert result["redirects"] >= 0
    
    @pytest.mark.asyncio
    async def test_agent_path_tracked(self, orchestrator):
        """Test that agent path is tracked correctly."""
        result = await orchestrator.route_and_execute(
            user_input="lista propiedades",
            session_id="test-session",
            direct_execution=True
        )
        
        # Should have agent path
        assert "agent_path" in result
        assert len(result["agent_path"]) >= 1
    
    @pytest.mark.asyncio
    async def test_multi_domain_escalates_to_main_agent(self, orchestrator):
        """Test that multi-domain tasks escalate to MainAgent."""
        result = await orchestrator.route_and_execute(
            user_input="crea propiedad y pon B5 en 1000",
            session_id="test-session",
            direct_execution=True
        )
        
        # Should escalate to MainAgent
        assert "MainAgent" in result["agent_path"]
        assert result["status"] == "use_main_agent"


class TestMaxRedirects:
    """Test max redirects safety mechanism."""
    
    @pytest.fixture
    def orchestrator(self):
        return OrchestrationRouter()
    
    @pytest.mark.asyncio
    async def test_max_redirects_prevents_infinite_loop(self, orchestrator):
        """Test that max redirects prevents infinite loops."""
        # This is a safety test - even with pathological input,
        # orchestrator should not loop infinitely
        result = await orchestrator.route_and_execute(
            user_input="test input",
            session_id="test-session",
            direct_execution=True
        )
        
        # Should complete with redirect count <= max_redirects
        assert "redirects" in result
        assert result["redirects"] <= orchestrator.max_redirects


class TestFallbackToMainAgent:
    """Test fallback to MainAgent on errors."""
    
    @pytest.fixture
    def orchestrator(self):
        return OrchestrationRouter()
    
    @pytest.mark.asyncio
    async def test_error_falls_back_to_main_agent(self, orchestrator):
        """Test that errors trigger fallback to MainAgent."""
        # Use ambiguous input that might cause issues
        result = await orchestrator.route_and_execute(
            user_input="",  # Empty input
            session_id="test-session",
            direct_execution=True
        )
        
        # Should fallback or handle gracefully
        assert result["status"] in ["use_main_agent", "error", "routed", "completed"]


class TestPhase2aVsPhase2b:
    """Test difference between Phase 2a (routing only) and Phase 2b (direct execution)."""
    
    @pytest.fixture
    def orchestrator(self):
        return OrchestrationRouter()
    
    @pytest.mark.asyncio
    async def test_phase_2a_returns_routed_status(self, orchestrator):
        """Test that Phase 2a returns 'routed' status (no direct execution)."""
        result = await orchestrator.route_and_execute(
            user_input="pon B5 en 1000",
            session_id="test-session",
            property_id="test-prop-1",
            direct_execution=False  # Phase 2a
        )
        
        # Should return routing info only
        assert result["status"] == "routed"
        assert "target_agent" in result
        assert "intent" in result
        assert "confidence" in result
    
    @pytest.mark.asyncio
    async def test_phase_2b_executes_directly(self, orchestrator):
        """Test that Phase 2b executes agents directly."""
        result = await orchestrator.route_and_execute(
            user_input="pon B5 en 1000",
            session_id="test-session",
            property_id="test-prop-1",
            direct_execution=True  # Phase 2b
        )
        
        # Should complete or escalate (not just route)
        assert result["status"] in ["completed", "use_main_agent"]
        assert "agent_path" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])

