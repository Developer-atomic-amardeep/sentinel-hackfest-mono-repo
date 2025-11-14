'use client'

import React, { useEffect, useRef, useState } from "react"
import ReactMarkdown from "react-markdown"
import { Button } from "@/components/ui/button"
import { Send, Menu, X, Settings, Moon, LogOut, Plus, Trash2, Mic, Paperclip, FileText, Image as ImageIcon, File } from "lucide-react"
import { useToast } from "@/hooks/use-toast"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:9000"
const AGORA_CHANNEL = process.env.NEXT_PUBLIC_AGORA_CHANNEL || "hackfest-sentinel"

interface ChatMessage {
  id: string
  text: string
  sender: "user" | "bot"
  timestamp: Date
  files?: Array<{ name: string; type: string; size: number }>
}

interface ChatSession {
  id: string
  title: string
  messages: ChatMessage[]
  updatedAt: Date
}

interface ChatbotPageProps {
  userInfo: any
  onLogout: () => void
}

declare global {
  interface Window {
    webkitSpeechRecognition?: any
    SpeechRecognition?: any
  }
}

export function ChatbotPage({ userInfo, onLogout }: ChatbotPageProps) {
  const [chatSessions, setChatSessions] = useState<ChatSession[]>([])
  const [currentChatId, setCurrentChatId] = useState<string | null>(null)
  const [messages, setMessages] = useState<ChatMessage[]>([])
  const [inputValue, setInputValue] = useState("")
  const [isLoading, setIsLoading] = useState(false)
  const [sidebarOpen, setSidebarOpen] = useState(true)
  const [darkMode, setDarkMode] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [attachedFiles, setAttachedFiles] = useState<File[]>([])
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)
  const { toast } = useToast()

  const [isListening, setIsListening] = useState(false)
  const [isSpeechSupported, setIsSpeechSupported] = useState(true)
  const recognitionRef = useRef<any>(null)

  const lastFinalRef = useRef<string>("")
  const committedRef = useRef<string>("")
  const isStartingRef = useRef<boolean>(false)

  const textareaRef = useRef<HTMLTextAreaElement | null>(null)

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" })
  }

  useEffect(() => {
    scrollToBottom()
  }, [messages])

  useEffect(() => {
    const ta = textareaRef.current
    if (!ta) return
    ta.style.height = "auto"
    requestAnimationFrame(() => {
      ta.style.height = `${Math.max(40, ta.scrollHeight)}px`
    })
  }, [inputValue])

  useEffect(() => {
    loadChatHistories()
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  useEffect(() => {
    const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition
    if (!SpeechRecognition) {
      setIsSpeechSupported(false)
      console.warn("SpeechRecognition API not supported in this browser.")
      return
    }

    const recognition = new SpeechRecognition()
    recognition.lang = "en-IN"
    recognition.interimResults = true
    recognition.maxAlternatives = 1
    recognition.continuous = true

    recognition.onresult = (event: SpeechRecognitionEvent) => {
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

      if (finalTranscript) {
        const cleanedFinal = finalTranscript.trim()
        if (cleanedFinal && cleanedFinal !== lastFinalRef.current) {
          committedRef.current = (committedRef.current + " " + cleanedFinal).trim()
          lastFinalRef.current = cleanedFinal
          setInputValue(committedRef.current)
        }
      } else if (interim) {
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
      if (isListening) {
        try {
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
      try {
        recognition.stop()
      } catch {}
      setIsListening(false)
      isStartingRef.current = false
      return
    }

    try {
      if (!isStartingRef.current) {
        isStartingRef.current = true
        recognition.start()
        setIsListening(true)
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
            updatedAt: new Date(history.updated_at || history.created_at),
            messages: messagesData.messages.map((msg: any) => ({
              id: msg.id.toString(),
              text: msg.content,
              sender: msg.role === "assistant" ? "bot" : "user",
              timestamp: new Date(msg.created_at),
            })),
          }
        })
      )

      // Sort by most recent first
      sessions.sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime())

      setChatSessions(sessions)
      
      // Always create a new chat when user logs in
      await handleNewChat()
    } catch (error) {
      console.error("Error loading chat histories:", error)
      handleNewChat()
    }
  }

  const getFileIcon = (fileName: string) => {
    const ext = fileName.split('.').pop()?.toLowerCase()
    if (['jpg', 'jpeg', 'png', 'gif', 'webp'].includes(ext || '')) {
      return <ImageIcon className="w-4 h-4" />
    } else if (['pdf', 'doc', 'docx', 'txt'].includes(ext || '')) {
      return <FileText className="w-4 h-4" />
    }
    return <File className="w-4 h-4" />
  }

  const formatFileSize = (bytes: number) => {
    if (bytes < 1024) return bytes + ' B'
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB'
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB'
  }

  const handleSendMessage = async (e?: React.FormEvent) => {
    if (e) e.preventDefault()
    if ((!inputValue.trim() && attachedFiles.length === 0) || !currentChatId) return

    const fileInfo = attachedFiles.map(f => ({
      name: f.name,
      type: f.type,
      size: f.size
    }))

    const messageText = inputValue.trim() || "Uploaded files"
    const userMessage: ChatMessage = {
      id: Date.now().toString(),
      text: messageText,
      sender: "user",
      timestamp: new Date(),
      files: fileInfo.length > 0 ? fileInfo : undefined
    }

    const updatedMessages = [...messages, userMessage]
    setMessages(updatedMessages)
    
    // Update the chat session in the sidebar with new message
    setChatSessions(prev => prev.map(chat => 
      chat.id === currentChatId 
        ? { ...chat, messages: updatedMessages, updatedAt: new Date() }
        : chat
    ).sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime()))
    
    const messageCopy = messageText
    const filesCopy = [...attachedFiles]
    
    setInputValue("")
    committedRef.current = ""
    lastFinalRef.current = ""
    setAttachedFiles([])
    
    setIsLoading(true)

    try {
      let uploadedFilePaths: string[] = []
      if (filesCopy.length > 0) {
        const formData = new FormData()
        filesCopy.forEach(file => {
          formData.append('files', file)
        })

        try {
          const uploadResponse = await fetch(`${API_URL}/upload-files`, {
            method: "POST",
            body: formData,
          })

          if (uploadResponse.ok) {
            const uploadResult = await uploadResponse.json()
            uploadedFilePaths = uploadResult.file_paths || []
          } else {
            console.warn("File upload failed, continuing without files")
          }
        } catch (uploadErr) {
          console.error("Error uploading files:", uploadErr)
        }
      }

      const saveResponse = await fetch(`${API_URL}/chat-histories/${currentChatId}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          role: "user",
          content: messageCopy,
        }),
      })

      if (!saveResponse.ok) throw new Error("Failed to save message")

      const streamRes = await fetch(`${API_URL}/analyze-query-stream`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ 
          user_query: messageCopy,
          file_paths: uploadedFilePaths
        }),
      })

      if (!streamRes.ok) {
        throw new Error("Streaming endpoint returned an error")
      }

      const reader = streamRes.body!.getReader()
      const decoder = new TextDecoder()

      let accumulatedResponse = ""
      let botMessageId = (Date.now() + Math.random()).toString()

      while (true) {
        const { done, value } = await reader.read()
        if (done) break

        const chunk = decoder.decode(value)
        const lines = chunk.split("\n")

        for (const line of lines) {
          if (!line.startsWith("data: ")) continue
          try {
            const data = JSON.parse(line.slice(6))

            if (data.chunk) {
              accumulatedResponse += data.chunk
              
              setMessages((prev) => {
                const existing = prev.find(m => m.id === botMessageId)
                const newMessages = existing
                  ? prev.map(m => m.id === botMessageId ? { ...m, text: accumulatedResponse } : m)
                  : [...prev, {
                      id: botMessageId,
                      text: accumulatedResponse,
                      sender: "bot" as const,
                      timestamp: new Date(),
                    }]
                
                // Update sidebar chat session
                setChatSessions(prevSessions => prevSessions.map(chat => 
                  chat.id === currentChatId 
                    ? { ...chat, messages: newMessages, updatedAt: new Date() }
                    : chat
                ).sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime()))
                
                return newMessages
              })
              scrollToBottom()
            }

            if (data.final_response) {
              const finalText = data.final_response

              setMessages((prev) => {
                const existing = prev.find(m => m.id === botMessageId)
                const finalMessages = existing
                  ? prev.map(m => m.id === botMessageId ? { ...m, text: finalText } : m)
                  : [...prev, {
                      id: botMessageId,
                      text: finalText,
                      sender: "bot" as const,
                      timestamp: new Date(),
                    }]
                
                // Final update to sidebar
                setChatSessions(prevSessions => prevSessions.map(chat => 
                  chat.id === currentChatId 
                    ? { ...chat, messages: finalMessages, updatedAt: new Date() }
                    : chat
                ).sort((a, b) => b.updatedAt.getTime() - a.updatedAt.getTime()))
                
                return finalMessages
              })

              await fetch(`${API_URL}/chat-histories/${currentChatId}/messages`, {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                  role: "assistant",
                  content: finalText,
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
        updatedAt: new Date(),
      }

      setChatSessions((prev) => [newChat, ...prev])
      setCurrentChatId(newChat.id)
      setMessages([])

      committedRef.current = ""
      lastFinalRef.current = ""
      setInputValue("")
      setAttachedFiles([])
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

      committedRef.current = ""
      lastFinalRef.current = ""
      setInputValue("")
      setAttachedFiles([])
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

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const files = e.target.files
    if (files) {
      const newFiles = Array.from(files)
      setAttachedFiles((prev) => [...prev, ...newFiles])
      
      toast({
        title: "Files attached",
        description: `${newFiles.length} file(s) ready to send`,
      })
    }
    if (fileInputRef.current) {
      fileInputRef.current.value = ""
    }
  }

  const removeAttachedFile = (index: number) => {
    setAttachedFiles((prev) => prev.filter((_, i) => i !== index))
  }

  const handleKeyDown = (e: React.KeyboardEvent<HTMLTextAreaElement>) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault()
      handleSendMessage()
    }
  }

  return (
    <div className={`flex h-screen ${darkMode ? "bg-gray-900" : "bg-white"}`}>
      <div className={`flex-1 flex ${showSettings ? "pointer-events-none" : "pointer-events-auto"}`}>
        <aside className={`${sidebarOpen ? "w-72" : "w-0"} transition-all duration-300 ${darkMode ? "bg-gray-800" : "bg-gray-50"} border-r ${darkMode ? "border-gray-700" : "border-gray-200"} overflow-hidden flex flex-col shadow-sm`}>
          <div className="p-4">
            <Button onClick={handleNewChat} className="w-full flex items-center justify-center gap-2 bg-teal-600 hover:bg-teal-700 text-white rounded-lg py-2 shadow">
              <Plus className="w-4 h-4" />
              New chat
            </Button>
          </div>

          <div className="flex-1 overflow-y-auto px-4 py-2 scrollbar-hide">
            {chatSessions.length > 0 && (
              <div className="text-xs text-gray-500 font-semibold mb-3 uppercase tracking-wide">Chat History</div>
            )}
            <div className="space-y-0">
              {chatSessions.map((chat, index) => (
                <React.Fragment key={chat.id}>
                  <div className="flex items-center gap-2 group py-1">
                    <button 
                      onClick={() => handleSelectChat(chat.id)} 
                      className={`flex-1 text-left px-3 py-2.5 rounded-lg text-sm transition-all ${
                        currentChatId === chat.id 
                          ? (darkMode ? "bg-teal-700 text-white shadow-sm" : "bg-teal-100 text-teal-900 shadow-sm") 
                          : (darkMode ? "hover:bg-gray-700 text-gray-300" : "hover:bg-gray-200 text-gray-700")
                      }`}
                    >
                      <div className="truncate font-medium">{chat.title}</div>
                      <div className={`text-xs mt-1 ${
                        currentChatId === chat.id 
                          ? (darkMode ? "text-teal-200" : "text-teal-700")
                          : (darkMode ? "text-gray-500" : "text-gray-500")
                      }`}>
                        {chat.messages.length} message{chat.messages.length !== 1 ? 's' : ''}
                      </div>
                    </button>
                    <button 
                      onClick={() => handleDeleteChat(chat.id)} 
                      aria-label={`Delete chat ${chat.title}`} 
                      className={`p-1.5 rounded opacity-0 group-hover:opacity-100 transition-opacity ${
                        darkMode ? "hover:bg-gray-700" : "hover:bg-gray-200"
                      }`}
                    >
                      <Trash2 className="w-4 h-4 text-red-500" />
                    </button>
                  </div>
                  {index < chatSessions.length - 1 && (
                    <div className={`my-2 border-t ${darkMode ? "border-gray-700" : "border-gray-200"}`} />
                  )}
                </React.Fragment>
              ))}
            </div>
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

          <div className="flex-1 overflow-y-auto p-6 space-y-4 scrollbar-hide">
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
                      {message.files && message.files.length > 0 && (
                        <div className="mb-2 space-y-1">
                          {message.files.map((file, idx) => (
                            <div key={idx} className={`flex items-center gap-2 text-xs px-2 py-1 rounded ${message.sender === "user" ? "bg-teal-700" : darkMode ? "bg-gray-600" : "bg-gray-200"}`}>
                              {getFileIcon(file.name)}
                              <span className="flex-1 truncate">{file.name}</span>
                              <span className="text-xs opacity-70">{formatFileSize(file.size)}</span>
                            </div>
                          ))}
                        </div>
                      )}
                      <div className="prose prose-sm max-w-none dark:prose-invert text-sm"><ReactMarkdown>{message.text}</ReactMarkdown></div>
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

          <div className={`px-6 py-4 border-t ${darkMode ? "bg-gray-800 border-gray-700" : "bg-white border-gray-200"}`}>
            <form onSubmit={handleSendMessage} className="space-y-3">
              {attachedFiles.length > 0 && (
                <div className="flex gap-2 flex-wrap">
                  {attachedFiles.map((file, idx) => (
                    <div key={idx} className="px-3 py-1.5 rounded-lg bg-teal-50 border border-teal-200 text-teal-700 text-xs flex items-center gap-2 shadow-sm">
                      {getFileIcon(file.name)}
                      <span className="max-w-[150px] truncate">{file.name}</span>
                      <span className="text-xs opacity-70">{formatFileSize(file.size)}</span>
                      <button type="button" onClick={() => removeAttachedFile(idx)} className="hover:text-teal-900 ml-1">×</button>
                    </div>
                  ))}
                </div>
              )}

              <div className="flex gap-2 items-end">
                <div className="flex-1 relative">
                  <textarea
                    ref={textareaRef}
                    value={inputValue}
                    onChange={(e) => {
                      setInputValue(e.target.value)
                      committedRef.current = e.target.value
                      lastFinalRef.current = ""
                      e.target.style.height = "auto"
                      e.target.style.height = `${Math.max(40, e.target.scrollHeight)}px`
                    }}
                    onKeyDown={handleKeyDown}
                    rows={1}
                    placeholder="Message our AI support assistant..."
                    aria-label="Message"
                    className={`w-full min-h-[40px] max-h-[240px] resize-none overflow-auto rounded-2xl px-4 py-2.5 pr-12 border transition-shadow focus:outline-none focus:ring-2 focus:ring-teal-500 placeholder:opacity-80 scrollbar-hide
                      ${darkMode ? "bg-gray-700 border-gray-600 text-white placeholder-gray-400" : "bg-white border-gray-200 text-gray-900"}`}
                    disabled={isLoading}
                    style={{ lineHeight: "1.25rem" }}
                  />
                  
                  <button 
                    type="button" 
                    onClick={() => fileInputRef.current?.click()} 
                    className={`absolute right-2 bottom-2 p-1.5 rounded-lg transition-colors ${darkMode ? "hover:bg-gray-600 text-gray-400" : "hover:bg-gray-100 text-gray-600"}`} 
                    title="Attach files"
                    disabled={isLoading}
                  >
                    <Paperclip className="w-5 h-5" />
                  </button>
                </div>

                <input 
                  ref={fileInputRef} 
                  type="file" 
                  multiple 
                  onChange={handleFileSelect} 
                  className="hidden" 
                  accept=".pdf,.doc,.docx,.txt,.png,.jpg,.jpeg" 
                />

                <button 
                  type="button" 
                  onClick={toggleListening} 
                  aria-pressed={isListening} 
                  disabled={isLoading}
                  className={`p-3 rounded-full transition-transform transform flex-shrink-0 ${isListening ? "scale-105 ring-4 ring-red-400/30 shadow-lg" : "hover:scale-105"} ${darkMode ? "bg-gradient-to-r from-blue-600 to-purple-600 text-white shadow" : "bg-gradient-to-r from-blue-500 to-purple-500 text-white shadow"}`} 
                  title="Voice recognition"
                >
                  <Mic className="w-5 h-5" />
                </button>

                <Button 
                  type="submit" 
                  disabled={isLoading || (!inputValue.trim() && attachedFiles.length === 0)} 
                  className="bg-teal-600 hover:bg-teal-700 text-white rounded-full p-3 shadow flex-shrink-0"
                >
                  <Send className="w-5 h-5" />
                </Button>
              </div>
            </form>
          </div>
        </main>
      </div>

      {showSettings && (
        <div
          role="dialog"
          aria-modal="true"
          aria-label="Settings"
          className="fixed inset-0 z-50 flex items-center justify-center"
        >
          <div
            onClick={() => setShowSettings(false)}
            className="absolute inset-0 bg-black/40 backdrop-blur-sm transition-opacity duration-200"
            aria-hidden="true"
          />

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
      
      <style jsx>{`
        @keyframes modalPop {
          from { opacity: 0; transform: translateY(6px) scale(.985); }
          to { opacity: 1; transform: translateY(0) scale(1); }
        }
        .scrollbar-hide::-webkit-scrollbar {
          display: none;
        }
        .scrollbar-hide {
          -ms-overflow-style: none;
          scrollbar-width: none;
        }
      `}</style>
    </div>
  )
}

export default ChatbotPage