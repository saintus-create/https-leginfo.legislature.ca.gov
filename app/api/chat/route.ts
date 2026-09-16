import { openai } from "@ai-sdk/openai";
import {
  streamText,
  convertToModelMessages,
  stepCountIs,
  tool,
  zodSchema,
} from "ai";
import type { UIMessage } from "ai";
import { z } from "zod";
import {
  AISDKToolkit,
  type AISDKToolkitToolsOptions,
} from "@assistant-ui/ai-sdk";
import {
  renderGuiToolDescription,
  renderGuiToolInputSchema,
} from "../../../lib/render-gui-tool";
import toolkit from "../../toolkit";

export const maxDuration = 30;

const aiToolkit = new AISDKToolkit({ toolkit });

// Your California Legislative AI backend URL
const LEGISLATIVE_AI_URL = "https://https-leginfo-legislature-ca-gov.ca-app.workers.dev";

type FrontendToolDefs = NonNullable<AISDKToolkitToolsOptions["frontend"]>;

export async function POST(req: Request) {
  const {
    messages,
    system,
    tools: clientTools,
  }: {
    messages: UIMessage[];
    system?: string;
    tools?: FrontendToolDefs;
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

    // Return the response through the UIMessageStream
    const result = streamText({
      model: openai("gpt-5.6-luna"),
      messages: await convertToModelMessages([
        ...messages.slice(0, -1),
        { role: "assistant", content: responseText }
      ]),
      stopWhen: stepCountIs(1),
      ...(system ? { system } : {}),
      tools: {
        render_gui: tool({
          description: renderGuiToolDescription,
          inputSchema: zodSchema(renderGuiToolInputSchema),
          execute: async (input) => ({
            spec: input.spec,
          }),
        }),
        generate_chart: tool({
          description:
            "Generate a chart. Return structured data for rendering a bar, line, or pie chart.",
          inputSchema: zodSchema(
            z.object({
              title: z.string().describe("Chart title"),
              type: z
                .enum(["bar", "line", "pie"])
                .describe("Chart type to render"),
              data: z
                .array(z.record(z.string(), z.union([z.string(), z.number()])))
                .describe(
                  "Array of data objects, e.g. [{month: 'Jan', revenue: 100}]",
                ),
              xKey: z
                .string()
                .describe("Key in each data object to use for the x-axis/labels"),
              dataKeys: z
                .array(z.string())
                .describe("Keys in each data object to chart as series/values"),
            }),
          ),
          execute: async () => ({ success: true }),
        }),
        show_location: tool({
          description:
            "Show a location on a map.",
          inputSchema: zodSchema(
            z.object({
              name: z.string().describe("Name of the place"),
              address: z.string().optional().describe("Street address"),
              lat: z.number().describe("Latitude"),
              lng: z.number().describe("Longitude"),
            }),
          ),
          execute: async () => ({ success: true }),
        }),
      },
    } as Parameters<typeof streamText>[0]);

    return result.toUIMessageStreamResponse();

  } catch (error) {
    console.error("Error calling Legislative AI:", error);
    
    // Fallback: return a simple assistant response
    const fallbackText = `California Legislative AI: ${String(error)}`;
    
    const result = streamText({
      model: openai("gpt-5.6-luna"),
      messages: await convertToModelMessages([
        ...messages.slice(0, -1),
        { role: "assistant", content: fallbackText }
      ]),
      stopWhen: stepCountIs(1),
      ...(system ? { system } : {}),
    });

    return result.toUIMessageStreamResponse();
  }
}
