"""LLM Factory - Provider-agnostic LLM initialization."""

from typing import Optional, List, Any
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.callbacks import BaseCallbackHandler

from config import settings


class LLMFactory:
    """
    Factory for creating LLM instances across different providers.
    
    Supported providers:
    - openai: GPT-4, GPT-4o, GPT-3.5-turbo
    - anthropic: Claude 3.5 Sonnet, Claude 3 Opus, Claude 3 Haiku
    - google: Gemini Pro, Gemini Ultra
    - azure: Azure OpenAI deployments
    - ollama: Local models (Llama, Mistral, etc.)
    - groq: Fast inference (Llama, Mixtral)
    
    Usage:
        llm = LLMFactory.create()  # Uses settings from .env
        llm = LLMFactory.create(provider="anthropic", model="claude-3-sonnet")
    """
    
    _instance: Optional[BaseChatModel] = None
    
    @classmethod
    def create(
        cls,
        provider: str = None,
        model: str = None,
        temperature: float = None,
        streaming: bool = False,
        callbacks: List[BaseCallbackHandler] = None,
        **kwargs
    ) -> BaseChatModel:
        """
        Create an LLM instance based on provider.
        
        Args:
            provider: LLM provider (openai, anthropic, google, azure, ollama, groq)
            model: Model name/ID
            temperature: Sampling temperature
            streaming: Enable streaming responses
            callbacks: LangChain callbacks for tracing
            **kwargs: Additional provider-specific arguments
        
        Returns:
            BaseChatModel instance
        """
        # Use settings if not provided
        provider = provider or settings.llm_provider
        model = model or settings.llm_model
        temperature = temperature if temperature is not None else settings.llm_temperature
        
        callbacks = callbacks or []
        
        # Route to appropriate provider
        if provider == "openai":
            return cls._create_openai(model, temperature, streaming, callbacks, **kwargs)
        
        elif provider == "anthropic":
            return cls._create_anthropic(model, temperature, streaming, callbacks, **kwargs)
        
        elif provider == "google":
            return cls._create_google(model, temperature, streaming, callbacks, **kwargs)
        
        elif provider == "azure":
            return cls._create_azure(model, temperature, streaming, callbacks, **kwargs)
        
        elif provider == "ollama":
            return cls._create_ollama(model, temperature, streaming, callbacks, **kwargs)
        
        elif provider == "groq":
            return cls._create_groq(model, temperature, streaming, callbacks, **kwargs)
        
        else:
            raise ValueError(f"Unsupported LLM provider: {provider}")
    
    @classmethod
    def _create_openai(
        cls,
        model: str,
        temperature: float,
        streaming: bool,
        callbacks: List[BaseCallbackHandler],
        **kwargs
    ) -> BaseChatModel:
        """Create OpenAI ChatGPT instance."""
        from langchain_openai import ChatOpenAI
        
        return ChatOpenAI(
            model=model,
            api_key=settings.openai_api_key,
            temperature=temperature,
            streaming=streaming,
            callbacks=callbacks,
            **kwargs
        )
    
    @classmethod
    def _create_anthropic(
        cls,
        model: str,
        temperature: float,
        streaming: bool,
        callbacks: List[BaseCallbackHandler],
        **kwargs
    ) -> BaseChatModel:
        """Create Anthropic Claude instance."""
        from langchain_anthropic import ChatAnthropic
        
        return ChatAnthropic(
            model=model,
            api_key=settings.anthropic_api_key,
            temperature=temperature,
            streaming=streaming,
            callbacks=callbacks,
            **kwargs
        )
    
    @classmethod
    def _create_google(
        cls,
        model: str,
        temperature: float,
        streaming: bool,
        callbacks: List[BaseCallbackHandler],
        **kwargs
    ) -> BaseChatModel:
        """Create Google Gemini instance."""
        from langchain_google_genai import ChatGoogleGenerativeAI
        
        return ChatGoogleGenerativeAI(
            model=model,
            google_api_key=settings.google_api_key,
            temperature=temperature,
            streaming=streaming,
            callbacks=callbacks,
            **kwargs
        )
    
    @classmethod
    def _create_azure(
        cls,
        model: str,
        temperature: float,
        streaming: bool,
        callbacks: List[BaseCallbackHandler],
        **kwargs
    ) -> BaseChatModel:
        """Create Azure OpenAI instance."""
        from langchain_openai import AzureChatOpenAI
        
        return AzureChatOpenAI(
            deployment_name=model,
            api_key=settings.azure_api_key,
            azure_endpoint=settings.azure_endpoint,
            api_version=settings.azure_api_version,
            temperature=temperature,
            streaming=streaming,
            callbacks=callbacks,
            **kwargs
        )
    
    @classmethod
    def _create_ollama(
        cls,
        model: str,
        temperature: float,
        streaming: bool,
        callbacks: List[BaseCallbackHandler],
        **kwargs
    ) -> BaseChatModel:
        """Create Ollama local model instance."""
        from langchain_ollama import ChatOllama
        
        return ChatOllama(
            model=model,
            base_url=settings.ollama_base_url,
            temperature=temperature,
            callbacks=callbacks,
            **kwargs
        )
    
    @classmethod
    def _create_groq(
        cls,
        model: str,
        temperature: float,
        streaming: bool,
        callbacks: List[BaseCallbackHandler],
        **kwargs
    ) -> BaseChatModel:
        """Create Groq instance for fast inference."""
        from langchain_groq import ChatGroq
        
        return ChatGroq(
            model=model,
            api_key=settings.groq_api_key,
            temperature=temperature,
            streaming=streaming,
            callbacks=callbacks,
            **kwargs
        )
    
    @classmethod
    def get_default(cls) -> BaseChatModel:
        """Get or create singleton default LLM instance."""
        if cls._instance is None:
            cls._instance = cls.create()
        return cls._instance
    
    @classmethod
    def reset(cls):
        """Reset the singleton instance (useful for testing)."""
        cls._instance = None


def get_llm(
    streaming: bool = False,
    callbacks: List[BaseCallbackHandler] = None,
    **kwargs
) -> BaseChatModel:
    """
    Convenience function to get an LLM instance.
    
    Usage:
        llm = get_llm()
        llm = get_llm(streaming=True, callbacks=[handler])
    """
    return LLMFactory.create(
        streaming=streaming,
        callbacks=callbacks,
        **kwargs
    )
