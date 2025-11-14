
'use client'

import React, { useEffect, useRef, useState } from "react"
import { Button } from "@/components/ui/button"
import { Send, Menu, X, Settings, Moon, LogOut, Plus, Upload, Trash2, Mic } from "lucide-react"
import { useToast } from "@/hooks/use-toast"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:9000"
const AGORA_CHANNEL = process.env.NEXT_PUBLIC_AGORA_CHANNEL || "hackfest-sentinel"

interface ChatMessage {
  id: string
  text: string
  sender: "user" | "bot"
  timestamp: Date
}

interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
}

interface ChatbotPageProps {
  userInfo: any
  onLogout: () => void
}

/**
 * Small typings to avoid TS errors on window.SpeechRecognition / webkitSpeechRecognition
 */
declare global {
  interface Window {
    webkitSpeechRecognition?: any
    SpeechRecognition?: any
  }
}

export function ChatbotPage({ userInfo, onLogout }: ChatbotPageProps) {
  // Chat state
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([])
  const [currentChatId, setCurrentChatId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [darkMode, setDarkMode] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [uploadedFiles, setUploadedFiles] = useState<string[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { toast } = useToast()

  // Voice recognition state (Option A: continuous live voice typing)
  const [isListening, setIsListening] = useState(false)
  const [isSpeechSupported, setIsSpeechSupported] = useState(true)
  const recognitionRef = useRef<any>(null)

  // Refs to manage transcripts & prevent overwrites
  const lastFinalRef = useRef<string>("")       // last final chunk text (used to reduce duplicates)
  const committedRef = useRef<string>("")       // committed final transcript that should persist in input
  const isStartingRef = useRef<boolean>(false)  // prevents rapid double-start

  // Textarea ref for auto-resize
  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  // Scroll helper
  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  // Ensure textarea height sync when inputValue changes (including speech interim results)
  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = "auto"
    // small delay to let fonts render properly
    requestAnimationFrame(() => {
      ta.style.height = `${Math.max(40, ta.scrollHeight)}px`
    })
  }, [inputValue])

  // Load chat histories once
  useEffect(() => {
    loadChatHistories()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Initialize Web Speech API (SpeechRecognition)
  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      setIsSpeechSupported(false)
      console.warn("SpeechRecognition API not supported in this browser.")
      return
    }

    const recognition = new SpeechRecognition()
    recognition.lang = "en-IN" // change as needed
    recognition.interimResults = true
    recognition.maxAlternatives = 1
    recognition.continuous = true // continuous for Option A

    recognition.onresult = (event: SpeechRecognitionEvent) => {
      // Build transcript from results
      let interim = ""
      let finalTranscript = ""
      for (let i = event.resultIndex; i < event.results.length; ++i) {
        const res = event.results[i]
        if (res.isFinal) {
          finalTranscript += res[0].transcript
        } else {
          interim += res[0].transcript
        }
      }

      // If final text arrived — append to committedRef (do NOT overwrite previous committed text)
      if (finalTranscript) {
        const cleanedFinal = finalTranscript.trim()
        // Avoid exact duplicate appends
        if (cleanedFinal && cleanedFinal !== lastFinalRef.current) {
          // Append with a space separator, preserve previously committed text
          committedRef.current = (committedRef.current + " " + cleanedFinal).trim()
          lastFinalRef.current = cleanedFinal
          // Show only the committed text in the input (finalized)
          setInputValue(committedRef.current)
        }
      } else if (interim) {
        // Show interim merged with committed text (do not overwrite committedRef)
        const interimCombined = (committedRef.current + " " + interim).trim()
        setInputValue(interimCombined)
      }
    }

    recognition.onerror = (event: any) => {
      console.error("SpeechRecognition error", event)
      if (event.error === "not-allowed" || event.error === "service-not-allowed") {
        toast({
          title: "Microphone access denied",
          description: "Please allow microphone access for voice typing to work.",
          variant: "destructive",
        })
        setIsListening(false)
        try { recognition.stop() } catch {}
      }
    }

    recognition.onend = () => {
      // If listening remains true, restart recognition to keep continuous mode.
      // Use isStartingRef to prevent immediate double-start race conditions.
      if (isListening) {
        try {
          // small delay to allow browser to settle, prevents duplicate onresult triggers
          setTimeout(() => {
            try {
              if (isListening && recognitionRef.current) {
                isStartingRef.current = true
                recognitionRef.current.start()
              }
            } catch (e) {
              console.warn("Failed to restart recognition:", e)
              isStartingRef.current = false
            }
          }, 200)
        } catch (e) {
          console.warn("Failed to restart recognition (outer):", e)
        }
      } else {
        isStartingRef.current = false
      }
    }

    recognitionRef.current = recognition

    return () => {
      try { recognition.stop() } catch {}
      recognitionRef.current = null
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // Toggle microphone listening (Option A)
  const toggleListening = async () => {
    if (!isSpeechSupported) {
      toast({
        title: "Not supported",
        description: "Your browser doesn't support the Web Speech API.",
        variant: "destructive",
      })
      return
    }

    const recognition = recognitionRef.current
    if (!recognition) return

    if (isListening) {
      // stop listening — do NOT clear committed transcript; user should keep it until send/delete
      try {
        recognition.stop()
      } catch {}
      setIsListening(false)
      isStartingRef.current = false
      return
    }

    // Start listening safely (prevent double starts)
    try {
      if (!isStartingRef.current) {
        isStartingRef.current = true
        recognition.start()
        setIsListening(true)
        // do NOT reset committedRef here — keep any existing typed text
        // but reset lastFinalRef to avoid immediate duplicates from previous session
        lastFinalRef.current = ""
      }
    } catch (err) {
      console.error("Failed to start recognition", err)
      toast({
        title: "Error",
        description: "Could not start voice recognition. Check microphone permissions.",
        variant: "destructive",
      })
      setIsListening(false)
      isStartingRef.current = false
    }
  }

  // -------------------------
  // Backend interaction
  // -------------------------
  const loadChatHistories = async () => {
    try {
      const response = await fetch(`${API_URL}/chat-histories/${userInfo?.id}`)
      if (!response.ok) throw new Error("Failed to load chat histories")

      const histories = await response.json()

      const sessions = await Promise.all(
        histories.map(async (history: any) => {
          const messagesResponse = await fetch(`${API_URL}/chat-histories/${history.id}/messages`)
          const messagesData = await messagesResponse.json()
          return {
            id: history.id.toString(),
            title: history.title,
            messages: messagesData.messages.map((msg: any) => ({
              id: msg.id.toString(),
              text: msg.content,
              sender: msg.role === "assistant" ? "bot" : "user",
              timestamp: new Date(msg.created_at),
            })),
          }
        })
      )

      // Store sessions but DO NOT auto-open any old chat.
      setChatSessions(sessions)

      // ALWAYS start a fresh new chat for the user when they arrive (Option 1)
      // This ensures the main panel is empty and the user begins with a fresh chat.
      // handleNewChat will create a new chat on backend and update local state.
      await handleNewChat()
    } catch (error) {
      console.error("Error loading chat histories:", error)
      // If something went wrong, still create a new chat so user has a fresh start.
      handleNewChat()
    }
  }

  const handleSendMessage = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!inputValue.trim() || !currentChatId) return

    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      text: inputValue,
      sender: "user",
      timestamp: new Date(),
    }

    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    const messageText = inputValue
    // Clear input and committed transcript immediately (user has sent it)
    setInputValue("")
    committedRef.current = ""
    lastFinalRef.current = ""
    setIsLoading(true)

    try {
      const saveResponse = await fetch(`${API_URL}/chat-histories/${currentChatId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: "user",
          content: messageText,
        }),
      })

      if (!saveResponse.ok) throw new Error("Failed to save message")

      // STREAMING: connect to analyze-query-stream SSE endpoint
      const streamRes = await fetch(`${API_URL}/analyze-query-stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_query: messageText }),
      })

      if (!streamRes.ok) {
        throw new Error("Streaming endpoint returned an error")
      }

      const reader = streamRes.body!.getReader()
      const decoder = new TextDecoder()

      let greetingShown = false

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split("\n")

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          try {
            const data = JSON.parse(line.slice(6))

            // Display greeting message (once)
            if (data.greeting_message && !greetingShown) {
              greetingShown = true
              const greetMessage: ChatMessage = {
                id: (Date.now() + Math.random()).toString(),
                text: data.greeting_message,
                sender: "bot",
                timestamp: new Date(),
              }
              setMessages((prev) => [...prev, greetMessage])
              scrollToBottom()
            }

            // Display final response (when available)
            if (data.final_response) {
              const botMessage: ChatMessage = {
                id: (Date.now() + Math.random() + 1).toString(),
                text: data.final_response,
                sender: "bot",
                timestamp: new Date(),
              }

              setMessages((prev) => [...prev, botMessage])

              // Persist bot message
              await fetch(`${API_URL}/chat-histories/${currentChatId}/messages`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  role: "assistant",
                  content: data.final_response,
                }),
              })

              setIsLoading(false)
              scrollToBottom()
            }
          } catch (err) {
            console.warn("Failed to parse SSE chunk", err)
          }
        }
      }
    } catch (error) {
      console.error("Error sending message:", error)
      toast({
        title: "Error",
        description: "Failed to send message",
        variant: "destructive",
      })
    } finally {
      setIsLoading(false)
    }
  }

  const handleNewChat = async () => {
    try {
      const response = await fetch(`${API_URL}/chat-histories`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ user_id: userInfo?.id }),
      })

      if (!response.ok) throw new Error("Failed to create chat")

      const newChatData = await response.json()

      const newChat: ChatSession = {
        id: newChatData.id.toString(),
        title: newChatData.title,
        messages: [],
      }

      setChatSessions((prev) => [newChat, ...prev])
      setCurrentChatId(newChat.id)
      setMessages([])

      // Reset input / transcript buffers for new chat
      committedRef.current = ""
      lastFinalRef.current = ""
      setInputValue("")
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to create new chat",
        variant: "destructive",
      })
    }
  }

  const handleSelectChat = (chatId: string) => {
    const selectedChat = chatSessions.find((chat) => chat.id === chatId)
    if (selectedChat) {
      setCurrentChatId(chatId)
      setMessages(selectedChat.messages)

      // Reset any live speech text in the input when switching to a historical chat
      committedRef.current = ""
      lastFinalRef.current = ""
      setInputValue("")
    }
  }

  const handleDeleteChat = async (chatId: string) => {
    try {
      const response = await fetch(`${API_URL}/chat-histories/${chatId}`, {
        method: "DELETE",
      })

      if (!response.ok) throw new Error("Failed to delete chat")

      setChatSessions((prev) => prev.filter((chat) => chat.id !== chatId))
      if (currentChatId === chatId) {
        const remaining = chatSessions.filter((chat) => chat.id !== chatId)
        if (remaining.length > 0) {
          handleSelectChat(remaining[0].id)
        } else {
          handleNewChat()
        }
      }
    } catch (error) {
      toast({
        title: "Error",
        description: "Failed to delete chat",
        variant: "destructive",
      })
    }
  }

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files) {
      Array.from(files).forEach((file) => {
        setUploadedFiles((prev) => [...prev, file.name])

        const fileMessage: ChatMessage = {
          id: Date.now().toString(),
          text: `📎 Document uploaded: ${file.name}`,
          sender: "user",
          timestamp: new Date(),
        }

        const updatedMessages = [...messages, fileMessage]
        setMessages(updatedMessages)

        setChatSessions((prev) =>
          prev.map((chat) => (chat.id === currentChatId ? { ...chat, messages: updatedMessages } : chat))
        )
      })
    }
  }

  // -------------------------
  // UI render (polished)
  // -------------------------
  return (
    <div className={`flex h-screen ${darkMode ? "bg-gray-900" : "bg-white"}`}>
      {/* Container that will be blurred when settings open */}
      <div className={`flex-1 flex ${showSettings ? "pointer-events-none" : "pointer-events-auto"}`}>
        {/* Sidebar */}
        <aside className={`${sidebarOpen ? "w-72" : "w-0"} transition-all duration-300 ${darkMode ? "bg-gray-800" : "bg-gray-50"} border-r ${darkMode ? "border-gray-700" : "border-gray-200"} overflow-hidden flex flex-col shadow-sm`}>
          <div className="p-4">
            <Button onClick={handleNewChat} className="w-full flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg py-2 shadow">
              <Plus className="w-4 h-4" />
              New chat
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 space-y-3 py-2">
            {chatSessions.length > 0 && <div className="text-xs text-gray-500 font-semibold mb-2 uppercase">Chat History</div>}
            {chatSessions.map((chat) => (
              <div key={chat.id} className="flex items-center gap-2 group">
                <button onClick={() => handleSelectChat(chat.id)} className={`flex-1 text-left px-3 py-2 rounded-lg text-sm transition-colors ${currentChatId === chat.id ? (darkMode ? "bg-teal-700 text-white" : "bg-teal-100 text-teal-900") : (darkMode ? "hover:bg-gray-700 text-gray-300" : "hover:bg-gray-200 text-gray-700")}`}>
                  {chat.title}
                </button>
                <button onClick={() => handleDeleteChat(chat.id)} aria-label={`Delete chat ${chat.title}`} className={`p-1 rounded opacity-0 group-hover:opacity-100 transition-opacity ${darkMode ? "hover:bg-gray-700" : "hover:bg-gray-200"}`}>
                  <Trash2 className="w-4 h-4 text-red-500" />
                </button>
              </div>
            ))}
          </div>

          <div className={`p-4 border-t ${darkMode ? "border-gray-700" : "border-gray-200"} space-y-2`}>
            <Button variant="ghost" onClick={() => setDarkMode(!darkMode)} className={`w-full justify-start gap-2 ${darkMode ? "text-gray-300 hover:bg-gray-700" : "text-gray-700 hover:bg-gray-200"}`}>
              <Moon className="w-4 h-4" />
              {darkMode ? "Light mode" : "Dark mode"}
            </Button>
            <Button variant="ghost" onClick={() => setShowSettings(true)} className={`w-full justify-start gap-2 ${darkMode ? "text-gray-300 hover:bg-gray-700" : "text-gray-700 hover:bg-gray-200"}`}>
              <Settings className="w-4 h-4" />
              Settings
            </Button>
            <Button variant="ghost" onClick={onLogout} className="w-full justify-start gap-2 text-red-600 hover:bg-red-50">
              <LogOut className="w-4 h-4" />
              Logout
            </Button>
          </div>
        </aside>

        {/* Main area */}
        <main className={`flex-1 flex flex-col transition-all duration-300 ${showSettings ? "blur-sm" : ""}`}>
          <header className={`flex items-center justify-between px-6 py-4 border-b ${darkMode ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"}`}>
            <div className="flex items-center gap-4">
              <button onClick={() => setSidebarOpen(!sidebarOpen)} className={`p-2 rounded-lg ${darkMode ? "hover:bg-gray-700 text-gray-300" : "hover:bg-gray-100 text-gray-700"}`}>
                {sidebarOpen ? <X className="w-5 h-5" /> : <Menu className="w-5 h-5" />}
              </button>
              <h1 className={`text-xl font-semibold ${darkMode ? "text-white" : "text-gray-900"}`}>Smart Customer Support</h1>
            </div>
            <div className={`text-sm ${darkMode ? "text-gray-400" : "text-gray-600"}`}>Welcome, {userInfo?.name}</div>
          </header>

          {/* Chat content */}
          <div className="flex-1 overflow-y-auto p-6 space-y-4">
            {messages.length === 0 ? (
              <div className="h-full flex flex-col items-center justify-center gap-4">
                <div className={`text-5xl ${darkMode ? "text-gray-600" : "text-gray-300"}`}>✈️</div>
                <h2 className={`text-2xl font-semibold ${darkMode ? "text-gray-200" : "text-gray-900"}`}>Start a conversation</h2>
                <p className={`text-center max-w-sm ${darkMode ? "text-gray-400" : "text-gray-600"}`}>Ask our AI assistant anything about your issues and we'll help resolve them quickly with voice and text support. You can also upload documents for faster resolution.</p>
              </div>
            ) : (
              <>
                {messages.map((message) => (
                  <div key={message.id} className={`flex ${message.sender === "user" ? "justify-end" : "justify-start"}`}>
                    <div className={`max-w-xs lg:max-w-md px-4 py-2 rounded-lg shadow-sm ${message.sender === "user" ? "bg-teal-600 text-white" : darkMode ? "bg-gray-700 text-gray-100" : "bg-gray-100 text-gray-900"}`}>
                      <p className="text-sm whitespace-pre-wrap">{message.text}</p>
                      <span className={`text-xs mt-1 block ${message.sender === "user" ? "text-teal-100" : darkMode ? "text-gray-400" : "text-gray-500"}`}>
                        {message.timestamp.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}
                      </span>
                    </div>
                  </div>
                ))}
                {isLoading && (
                  <div className="flex justify-start">
                    <div className={`px-4 py-2 rounded-lg ${darkMode ? "bg-gray-700" : "bg-gray-100"}`}>
                      <div className="flex gap-2">
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" />
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.2s" }} />
                        <div className="w-2 h-2 bg-gray-400 rounded-full animate-bounce" style={{ animationDelay: "0.4s" }} />
                      </div>
                    </div>
                  </div>
                )}
                <div ref={messagesEndRef} />
              </>
            )}
          </div>

          {/* Composer */}
          <div className={`px-6 py-4 border-t ${darkMode ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"}`}>
            <form onSubmit={handleSendMessage} className="space-y-3">
              {uploadedFiles.length > 0 && (
                <div className="flex gap-2 flex-wrap">
                  {uploadedFiles.map((file, idx) => (
                    <div key={idx} className="px-3 py-1 rounded-full bg-teal-100 text-teal-700 text-xs flex items-center gap-2 shadow-sm">
                      📎 {file}
                      <button type="button" onClick={() => setUploadedFiles((prev) => prev.filter((_, i) => i !== idx))} className="hover:text-teal-900">×</button>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex gap-3 items-end">
                <div className="flex items-center gap-2">
                  <button type="button" onClick={() => fileInputRef.current?.click()} className={`p-2.5 rounded-lg transition-colors ${darkMode ? "bg-gray-700 hover:bg-gray-600 text-gray-300" : "bg-gray-100 hover:bg-gray-200 text-gray-700"}`} title="Upload document">
                    <Upload className="w-5 h-5" />
                  </button>
                </div>

                <div className="flex-1">
                  <textarea
                    ref={textareaRef}
                    value={inputValue}
                    onChange={(e) => {
                      setInputValue(e.target.value)
                      // keep committedRef consistent with typed text so speech doesn't conflict
                      committedRef.current = e.target.value
                      lastFinalRef.current = ""
                      // auto-resize (ensure this matches the useEffect too)
                      e.target.style.height = "auto"
                      e.target.style.height = `${Math.max(40, e.target.scrollHeight)}px`
                    }}
                    rows={1}
                    placeholder="Message our AI support assistant..."
                    aria-label="Message"
                    className={`w-full min-h-[40px] max-h-[240px] resize-none overflow-auto rounded-2xl px-4 py-3 border transition-shadow focus:outline-none focus:ring-2 focus:ring-teal-500 placeholder:opacity-80
                      ${darkMode ? "bg-gray-700 border-gray-600 text-white placeholder-gray-400" : "bg-white border-gray-200 text-gray-900"}`}
                    disabled={isLoading}
                    style={{ lineHeight: "1.25rem" }}
                  />
                </div>

                <div className="flex items-center gap-3">
                  <button type="button" onClick={toggleListening} aria-pressed={isListening} className={`p-3 rounded-full transition-transform transform ${isListening ? "scale-105 ring-4 ring-red-400/30 shadow-lg" : "hover:scale-105"} ${darkMode ? "bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow" : "bg-gradient-to-r from-blue-500 to-purple-500 text-white shadow"}`} title="Voice recognition (continuous)">
                    <Mic className="w-6 h-6" />
                  </button>

                  <input ref={fileInputRef} type="file" multiple onChange={handleFileUpload} className="hidden" accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg" />

                  <Button type="submit" disabled={isLoading || !inputValue.trim()} className="bg-teal-600 hover:bg-teal-700 text-white rounded-full px-5 py-2 shadow">
                    <Send className="w-4 h-4" />
                  </Button>
                </div>
              </div>
            </form>
          </div>
        </main>
      </div>

      {/* Settings modal (full-screen overlay with backdrop blur & smooth transition) */}
      {showSettings && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Settings"
          className="fixed inset-0 z-50 flex items-center justify-center"
        >
          {/* Dimmed backdrop with gentle blur */}
          <div
            onClick={() => setShowSettings(false)}
            className="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity duration-200"
            aria-hidden="true"
          />

          {/* Modal panel */}
          <div className={`relative transform rounded-2xl p-6 max-w-md w-full mx-4 ${darkMode ? "bg-gray-800" : "bg-white"} shadow-2xl transition-all duration-200 ease-out`} style={{ animation: "modalPop .16s ease-out" }}>
            <div className="flex items-center justify-between mb-4">
              <h2 className={`text-2xl font-bold ${darkMode ? "text-white" : "text-gray-900"}`}>Settings</h2>
              <button onClick={() => setShowSettings(false)} className={`p-2 rounded-lg transition-colors ${darkMode ? "hover:bg-gray-700 text-gray-300" : "hover:bg-gray-100 text-gray-700"}`} aria-label="Close settings">
                <X className="w-5 h-5" />
              </button>
            </div>

            <div className="space-y-4">
              <div>
                <label className={`block text-sm font-semibold ${darkMode ? "text-gray-300" : "text-gray-700"} mb-2`}>Full Name</label>
                <div className={`px-4 py-2 rounded-lg ${darkMode ? "bg-gray-700 text-gray-100" : "bg-gray-100 text-gray-900"}`}>{userInfo?.name || "N/A"}</div>
              </div>

              <div>
                <label className={`block text-sm font-semibold ${darkMode ? "text-gray-300" : "text-gray-700"} mb-2`}>Contact Number</label>
                <div className={`px-4 py-2 rounded-lg ${darkMode ? "bg-gray-700 text-gray-100" : "bg-gray-100 text-gray-900"}`}>{userInfo?.phone_number || "N/A"}</div>
              </div>

              <div>
                <label className={`block text-sm font-semibold ${darkMode ? "text-gray-300" : "text-gray-700"} mb-2`}>Email Address</label>
                <div className={`px-4 py-2 rounded-lg ${darkMode ? "bg-gray-700 text-gray-100" : "bg-gray-100 text-gray-900"}`}>{userInfo?.email || "N/A"}</div>
              </div>
            </div>

            <div className="mt-6">
              <Button onClick={() => setShowSettings(false)} className="w-full mt-2 bg-teal-600 hover:bg-teal-700 text-white py-2 rounded-xl shadow">Close</Button>
            </div>
          </div>
        </div>
      )}
      {/* small inline keyframe for modal pop, purely CSS-inlined for simplicity */}
      <style jsx>{`
        @keyframes modalPop {
          from { opacity: 0; transform: translateY(6px) scale(.985); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
      `}</style>
    </div>
  )
}

export default ChatbotPage
