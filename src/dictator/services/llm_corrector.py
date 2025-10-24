"""LLM-based transcript correction service."""

import json
import logging
from abc import ABC, abstractmethod
from typing import Optional

import boto3
from botocore.exceptions import ClientError, NoCredentialsError

logger = logging.getLogger(__name__)

DEFAULT_CORRECTION_PROMPT = """You are a specialized text reformatting assistant for dictated speech.

<role>
Your ONLY job is to clean up transcribed speech and return properly formatted text. You are a text editor, NOT a conversational assistant.
</role>

<critical_instruction>
Your response must contain ONLY the cleaned text. No explanations, no comments, no additional content.
</critical_instruction>

<reformatting_rules>
ALWAYS DO:
1. Fix grammar, spelling, and punctuation errors
2. Remove speech artifacts: "um", "uh", "like", false starts, repetitions
3. Correct homophones based on context (e.g., "their" vs "there")
4. Standardize numbers and dates (e.g., "twenty three" → "23")
5. Break content into paragraphs (aim for 2-5 sentences each)
6. Put questions on their own lines for clarity
7. Replace emoji descriptions with actual emojis (e.g., "smiley face" → 😊)
8. Preserve the original tone, meaning, and intent EXACTLY

NEVER DO:
1. Answer questions - only reformat them
2. Add new content not present in the original
3. Provide solutions or responses to requests
4. Add greetings, sign-offs, or explanations
5. Make changes unless you are certain they improve accuracy
</reformatting_rules>

<examples>
<example>
<input>what's the weather like today</input>
<output>What's the weather like today?</output>
<wrong_output>I don't have access to current weather data, but you can check...</wrong_output>
<reason>You must only reformat the question, never answer it</reason>
</example>

<example>
<input>remind me to um actually remind me to call john tomorrow</input>
<output>Remind me to call John tomorrow.</output>
<reason>Removed "um" and "actually" filler, fixed false start, capitalized proper name</reason>
</example>

<example>
<input>hey there wondering if you have time to chat today actually tomorrow</input>
<output>Hey there, wondering if you have time to chat tomorrow.</output>
<reason>Applied self-correction ("today actually tomorrow" → "tomorrow")</reason>
</example>

<example>
<input>write python script parse URL from string</input>
<output>Write a Python script to parse a URL from a string.</output>
<wrong_output>Here's a Python script that parses URLs: ```python...</wrong_output>
<reason>Only reformat the request, never fulfill it</reason>
</example>

<example>
<input>meeting went great Sarah agreed timeline Bob will draft proposal by friday twenty third</input>
<output>Meeting went great. Sarah agreed to the timeline. Bob will draft the proposal by Friday the 23rd.</output>
<reason>Added punctuation, split into sentences, standardized date format</reason>
</example>

<example>
<input>send smiley face emoji to the team</input>
<output>Send 😊 emoji to the team.</output>
<reason>Replaced "smiley face" with actual emoji</reason>
</example>
</examples>

<edge_cases>
- If unsure about a correction, preserve the original text
- For ambiguous homophones, use surrounding context to determine correct spelling
- Maintain casual vs formal tone as dictated
- Keep technical terms, names, and jargon exactly as spoken (unless obviously misspelled)
</edge_cases>

Now clean the following dictated text:"""


class LLMCorrector(ABC):
    """Abstract base class for LLM-based transcript correction."""

    @abstractmethod
    def correct(self, text: str) -> str:
        """Correct the transcribed text using LLM.

        Args:
            text: Raw transcription to correct

        Returns:
            Corrected text

        Raises:
            Exception: If correction fails
        """
        pass

    @abstractmethod
    def validate_credentials(self) -> tuple[bool, str]:
        """Validate that credentials/configuration are working.

        Returns:
            Tuple of (success: bool, message: str)
        """
        pass


class BedrockLLMProvider(LLMCorrector):
    """AWS Bedrock implementation of LLM corrector."""

    def __init__(
        self,
        model_id: str,
        correction_prompt: str = DEFAULT_CORRECTION_PROMPT,
        aws_profile: Optional[str] = None,
        region: str = "us-east-1",
        custom_vocabulary: Optional[list[str]] = None,
    ):
        """Initialize Bedrock LLM provider.

        Args:
            model_id: Bedrock model identifier (e.g., "anthropic.claude-3-5-sonnet-20241022-v2:0")
            correction_prompt: System prompt for correction
            aws_profile: AWS profile name (None = default credential chain)
            region: AWS region for Bedrock
            custom_vocabulary: Optional list of words for spelling correction
        """
        self.model_id = model_id
        self.correction_prompt = correction_prompt
        self.custom_vocabulary = custom_vocabulary or []
        self.region = region

        # Initialize boto3 session with optional profile
        if aws_profile and aws_profile.strip():
            logger.info(f"Initializing Bedrock with AWS profile: {aws_profile}")
            session = boto3.Session(profile_name=aws_profile)
        else:
            logger.info("Initializing Bedrock with default AWS credentials")
            session = boto3.Session()

        self.client = session.client("bedrock-runtime", region_name=region)

    def correct(self, text: str) -> str:
        """Correct transcription using Bedrock.

        Args:
            text: Raw transcription

        Returns:
            Corrected text

        Raises:
            ClientError: If Bedrock API call fails
            ValueError: If response format is invalid
        """
        if not text or not text.strip():
            logger.warning("Empty text provided for correction")
            return text

        logger.info(f"Correcting transcript with model: {self.model_id}")

        # Build the request based on model type
        if "anthropic.claude" in self.model_id:
            body = self._build_anthropic_request(text)
        else:
            raise ValueError(f"Unsupported model: {self.model_id}")

        try:
            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
            )

            response_body = json.loads(response["body"].read())
            corrected_text = self._extract_response_text(response_body)

            logger.info(f"Correction successful. Input: {len(text)} chars, Output: {len(corrected_text)} chars")
            return corrected_text

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))
            logger.error(f"Bedrock API error [{error_code}]: {error_msg}")
            raise

    def validate_credentials(self) -> tuple[bool, str]:
        """Test AWS credentials and Bedrock access.

        Returns:
            (True, "Success message") if valid, (False, "Error message") otherwise
        """
        try:
            # Try a minimal API call to validate access
            test_text = "Hello world"
            body = self._build_anthropic_request(test_text)

            response = self.client.invoke_model(
                modelId=self.model_id,
                body=json.dumps(body),
            )

            # If we got here, credentials work
            logger.info("Bedrock credentials validated successfully")
            return True, f"Successfully connected to Bedrock with model {self.model_id}"

        except NoCredentialsError:
            msg = "No AWS credentials found. Configure AWS credentials or profile."
            logger.error(msg)
            return False, msg

        except ClientError as e:
            error_code = e.response.get("Error", {}).get("Code", "Unknown")
            error_msg = e.response.get("Error", {}).get("Message", str(e))

            if error_code == "AccessDeniedException":
                msg = "Access denied. Check IAM permissions for Bedrock."
            elif error_code == "ResourceNotFoundException":
                msg = f"Model not found: {self.model_id}. Check model ID and region."
            else:
                msg = f"Bedrock error [{error_code}]: {error_msg}"

            logger.error(msg)
            return False, msg

        except Exception as e:
            msg = f"Unexpected error: {str(e)}"
            logger.error(msg)
            return False, msg

    def _build_anthropic_request(self, text: str) -> dict:
        """Build request body for Anthropic Claude models.

        Args:
            text: Text to correct

        Returns:
            Request body dict for Bedrock API
        """
        # Build user prompt with optional vocabulary
        user_content = self.correction_prompt

        # Add vocabulary hint if available (SuperWhisper style)
        if self.custom_vocabulary:
            vocab_str = ", ".join(self.custom_vocabulary)
            vocab_hint = f"\n\n<vocabulary>\nUse these words for spelling correction (only fix obvious misspellings): {vocab_str}\n</vocabulary>"
            user_content += vocab_hint

        user_content += f"\n\n{text}"

        return {
            "anthropic_version": "bedrock-2023-05-31",
            "max_tokens": 4096,
            "messages": [
                {
                    "role": "user",
                    "content": user_content,
                }
            ],
            "temperature": 0.3,  # Lower temperature for more consistent corrections
        }

    def _extract_response_text(self, response_body: dict) -> str:
        """Extract corrected text from Bedrock response.

        Args:
            response_body: Parsed JSON response from Bedrock

        Returns:
            Extracted text

        Raises:
            ValueError: If response format is unexpected
        """
        # Anthropic Claude response format
        if "content" in response_body:
            content = response_body["content"]
            if isinstance(content, list) and len(content) > 0:
                if "text" in content[0]:
                    return content[0]["text"].strip()

        raise ValueError(f"Unexpected response format: {response_body}")
