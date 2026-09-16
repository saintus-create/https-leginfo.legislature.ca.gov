import { openai } from "@ai-sdk/openai";
import { frontendTools } from "@assistant-ui/react-ai-sdk";
import {
  JSONSchema7,
  streamText,
  convertToModelMessages,
  type UIMessage,
} from "ai";

// Your California Legislative AI backend URL
const LEGISLATIVE_AI_URL = "https://https-leginfo-legislature-ca-gov.ca-app.workers.dev";

export async function POST(req: Request) {
  const {
    messages,
    system,
    tools,
  }: {
    messages: UIMessage[];
    system?: string;
    tools?: Record<string, { description?: string; parameters: JSONSchema7 }>;
  } = await req.json();

  // Get the user's last message text
  const lastMessage = messages[messages.length - 1];
  const userMessage = typeof lastMessage.content === "string" 
    ? lastMessage.content 
    : JSON.stringify(lastMessage.content);

  // Call your California Legislative AI backend
  try {
    const backendResponse = await fetch(`${LEGISLATIVE_AI_URL}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: userMessage,
        messages: messages,
        system: system,
      }),
    });

    if (!backendResponse.ok) {
      throw new Error(`AI backend returned ${backendResponse.status}`);
    }

    const backendData = await backendResponse.json();
    
    // Extract response text from backend
    const responseText = typeof backendData === "string" 
      ? backendData 
      : backendData.response 
        ? backendData.response 
        : backendData.message 
          ? backendData.message
          : JSON.stringify(backendData);

    // Return the response through the stream
    const result = streamText({
      model: openai.responses("gpt-5-nano"),
      messages: await convertToModelMessages([
        ...messages.slice(0, -1),
        { role: "assistant", content: responseText }
      ]),
      system,
      tools: {
        ...frontendTools(tools ?? {}),
      },
      providerOptions: {
        openai: {
          reasoningEffort: "low",
          reasoningSummary: "auto",
        },
      },
    });

    return result.toUIMessageStreamResponse({
      sendReasoning: true,
    });

  } catch (error) {
    console.error("Error calling Legislative AI:", error);
    
    // Fallback response
    const fallbackText = `California Legislative AI response: ${String(error)}`;
    
    const result = streamText({
      model: openai.responses("gpt-5-nano"),
      messages: await convertToModelMessages([
        ...messages.slice(0, -1),
        { role: "assistant", content: fallbackText }
      ]),
      system,
      tools: {
        ...frontendTools(tools ?? {}),
      },
    });

    return result.toUIMessageStreamResponse({
      sendReasoning: true,
    });
  }
}
