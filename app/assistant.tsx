"use client";

import { AssistantRuntimeProvider } from "@assistant-ui/react";
import {
  useChatRuntime,
  AssistantChatTransport,
} from "@assistant-ui/ai-sdk";
import { lastAssistantMessageIsCompleteWithToolCalls } from "ai";
import { Thread } from "@/components/assistant-ui/thread";
import {
  AuiIf,
  ComposerPrimitive,
  MessagePrimitive,
  ThreadPrimitive,
} from "@assistant-ui/react";
import { cn } from "@/lib/utils";
import { MarkdownText } from "@/components/assistant-ui/markdown-text";

// Gemini Clone - Simplified for standalone use
export const Assistant = () => {
  const runtime = useChatRuntime({
    sendAutomaticallyWhen: lastAssistantMessageIsCompleteWithToolCalls,
    transport: new AssistantChatTransport({
      api: "/api/chat",
    }),
  });

  return (
    <AssistantRuntimeProvider runtime={runtime}>
      <div className="flex h-dvh w-full bg-[#fdfcfc] text-[#1f1f1f] dark:bg-[#0c0c0c] dark:text-[#e3e3e3]">
        <ThreadPrimitive.Root className="flex flex-1 flex-col overflow-hidden">
          {/* Empty State */}
          <AuiIf condition={(s) => s.thread.messages.length === 0}>
            <div className="relative flex grow flex-col items-center justify-center px-4">
              <div className="relative z-10 flex w-full max-w-3xl flex-col items-center">
                <h1 className="fade-in slide-in-from-bottom-3 motion-safe:animate-in fill-mode-both mb-6 text-center text-4xl font-normal delay-500 duration-400 ease-[cubic-bezier(0.22,1,0.36,1)] dark:text-white">
                  How can I help you today?
                </h1>
                <div className="relative w-full max-w-2xl">
                  {/* Ambient glow background */}
                  <div
                    aria-hidden="true"
                    className="fade-in zoom-in-40 blur-in-[90px] motion-safe:animate-in fill-mode-both pointer-events-none absolute top-1/2 left-1/2 h-[260px] w-[680px] max-w-[92%] -translate-x-1/2 -translate-y-1/2 rounded-[140px] bg-[#a9d1fb]/60 blur-[90px] duration-1000 ease-[cubic-bezier(0.22,1,0.36,1)] dark:bg-[#1b2f9c]/50"
                  />
                  <Composer />
                </div>
              </div>
            </div>
          </AuiIf>

          {/* Chat State */}
          <AuiIf condition={(s) => s.thread.messages.length > 0}>
            <ThreadPrimitive.Viewport className="flex grow flex-col overflow-y-scroll pt-12">
              <ThreadPrimitive.Messages 
                components={{ 
                  Message: ({ message }) => (
                    <div 
                      className={cn(
                        "flex w-full max-w-[85%] flex-col gap-2",
                        message.role === "user" ? "items-end" : "items-start"
                      )}
                    >
                      <div 
                        className={cn(
                          "rounded-3xl px-5 py-3",
                          message.role === "user" 
                            ? "bg-[#f2f0f0] dark:bg-[#333537]" 
                            : "bg-transparent"
                        )}
                      >
                        <MessagePrimitive.Parts components={{ Text: MarkdownText }} />
                      </div>
                    </div>
                  )
                }}
              />
              <ThreadPrimitive.ViewportFooter className="sticky bottom-0 mt-auto flex w-full flex-col items-center gap-1.5 bg-[#fdfcfc] px-4 pb-3 dark:bg-[#0c0c0c]">
                <Composer />
                <p className="text-center text-xs text-[#5e6063] dark:text-[#9aa0a6]">
                  Legislative AI can make mistakes, so double-check it.
                </p>
              </ThreadPrimitive.ViewportFooter>
            </ThreadPrimitive.Viewport>
          </AuiIf>
        </ThreadPrimitive.Root>
      </div>
    </AssistantRuntimeProvider>
  );
};

// Simplified Composer matching Gemini style
const Composer = () => {
  return (
    <ComposerPrimitive.Root className="mx-auto flex w-full max-w-2xl flex-col rounded-4xl bg-white p-3 dark:bg-[#1e1f20] shadow-[0_2px_10px_-2px_rgba(0,0,0,0.18)]">
      <AuiIf condition={(s) => s.composer.attachments.length > 0}>
        <ComposerPrimitive.Attachments />
      </AuiIf>
      
      <div className="flex items-end gap-1">
        <ComposerPrimitive.Input
          placeholder="Ask Legislative AI"
          className="flex-1 resize-none bg-transparent text-[17px] outline-none"
        />
        <ComposerPrimitive.Send className="flex shrink-0 items-center justify-center rounded-full bg-[#d3e3fd] text-[#062e6f] hover:bg-[#c8dff5] disabled:bg-[#e8eaed] disabled:text-[#1f1f1f]/40 transition-colors size-8">
          <svg className="size-4" fill="none" viewBox="0 0 24 24" stroke="currentColor">
            <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M5 12h14M5 12l7-7 7 7" />
          </svg>
        </ComposerPrimitive.Send>
      </div>
    </ComposerPrimitive.Root>
  );
};
