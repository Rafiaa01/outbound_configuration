from typing import Literal

from langchain_openai import ChatOpenAI
from pydantic import BaseModel


class IntentResult(BaseModel):
    intent: Literal["greeting", "policy", "unrelated", "goodbye"]


llm = ChatOpenAI(model="gpt-4o-mini", temperature=0)

intent_model = llm.with_structured_output(IntentResult)


async def classify_intent(message: str) -> str:

    result = await intent_model.ainvoke(
        [
            {
                "role": "system",
                "content": """
            Classify the user's message into exactly one category:

            1. greeting:
               Simple greetings and social conversation, such as
               hello, hi, hey, good morning, or how are you?

            2. policy:
               Questions about employee policies, including leave,
               attendance, payroll, benefits, working hours, holidays,
               probation, notice periods, and employee handbook rules.

            3. unrelated:
               Requests unrelated to employee policies or HR matters.

            4. goodbye:
               The user clearly wants to stop talking, end the
               conversation, or disconnect the call.

               Examples:
               - Goodbye.
               - Okay, bye.
               - I don't want to talk anymore.
               - I don't want to continue.
               - Please end the call.
               - I want to hang up.
               - That's all, thank you.
               - I have no more questions.
               - No, I'm done.

            Important rules:
            - A greeting followed by an HR question is policy.
            - Do not classify an HR question as unrelated.
            - "No" alone is not necessarily goodbye.
            - "I don't know" is not goodbye.
            - Only classify goodbye when the user clearly wants
              to end the conversation.
            """,
            },
            {"role": "user", "content": message},
        ]
    )

    return result.intent
