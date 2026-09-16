import {
  createUIMessageStream,
  createUIMessageStreamResponse,
} from "ai";

export const maxDuration = 30;

// Your California Legislative AI backend URL
const LEGISLATIVE_AI_URL = "https://https-leginfo-legislature-ca-gov.ca-app.workers.dev";

export async function POST(req: Request) {
  const { messages } = await req.json();

  // Get the user's last message
  const lastMessage = messages[messages.length - 1];
  const userMessage = typeof lastMessage.content === "string" 
    ? lastMessage.content 
    : JSON.stringify(lastMessage.content);

  // Call your California Legislative AI backend
  try {
    const response = await fetch(`${LEGISLATIVE_AI_URL}`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        message: userMessage,
        messages: messages,
      }),
    });

    if (!response.ok) {
      throw new Error(`AI backend returned ${response.status}`);
    }

    const data = await response.json();

    // Extract response text
    const responseText = typeof data === "string" 
      ? data 
      : data.response 
        ? data.response 
        : data.message 
          ? data.message
          : JSON.stringify(data);

    const stream = createUIMessageStream({
      originalMessages: messages,
      execute: async ({ writer }) => {
        const messageId = `msg-${crypto.randomUUID()}`;
        const textId = "response-text";

        writer.write({ type: "start", messageId });
        writer.write({ type: "start-step" });
        writer.write({ type: "text-start", id: textId });
        writer.write({
          type: "text-delta",
          id: textId,
          delta: responseText,
        });
        writer.write({ type: "text-end", id: textId });
        writer.write({ type: "finish-step" });
        writer.write({ type: "finish" });
      },
    });
    return createUIMessageStreamResponse({ stream });

  } catch (error) {
    console.error("Error calling Legislative AI:", error);
    
    // Fallback response
    const fallbackText = `California Legislative AI response: ${String(error)}`;
    
    const stream = createUIMessageStream({
      originalMessages: messages,
      execute: async ({ writer }) => {
        const messageId = `msg-${crypto.randomUUID()}`;
        const textId = "fallback-text";

        writer.write({ type: "start", messageId });
        writer.write({ type: "start-step" });
        writer.write({ type: "text-start", id: textId });
        writer.write({
          type: "text-delta",
          id: textId,
          delta: fallbackText,
        });
        writer.write({ type: "text-end", id: textId });
        writer.write({ type: "finish-step" });
        writer.write({ type: "finish" });
      },
    });
    return createUIMessageStreamResponse({ stream });
  }
}
