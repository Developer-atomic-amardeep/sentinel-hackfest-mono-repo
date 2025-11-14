const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

export interface User {
  id: number
  name: string
  email: string
  phone_number: string
}

export interface ChatHistory {
  id: number
  user_id: number
  title: string
  created_at: string
  message_count: number
}

export interface Message {
  id: number
  chat_history_id: number
  role: string
  content: string
  created_at: string
}

export interface ChatDetail {
  id: number
  user_id: number
  title: string
  created_at: string
  messages: Message[]
}

// User API
export async function validateUser(name: string, email: string, phone_number: string): Promise<User> {
  const response = await fetch(`${API_URL}/validate-users`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, phone_number }),
  })
  
  if (!response.ok) {
    const error = await response.json()
    throw new Error(error.detail?.join(", ") || "Validation failed")
  }
  
  return response.json()
}

export async function validateTestCredentials(name: string, email: string, phone_number: string) {
  const response = await fetch(`${API_URL}/test-credentials`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ name, email, phone_number }),
  })
  
  if (!response.ok) {
    throw new Error("Test credentials validation failed")
  }
  
  return response.json()
}

// Chat History API
export async function getUserChatHistories(userId: number): Promise<ChatHistory[]> {
  const response = await fetch(`${API_URL}/chat-histories/${userId}`)
  
  if (!response.ok) {
    throw new Error("Failed to fetch chat histories")
  }
  
  return response.json()
}

export async function createChatHistory(userId: number, title?: string): Promise<ChatHistory> {
  const response = await fetch(`${API_URL}/chat-histories`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ user_id: userId, title }),
  })
  
  if (!response.ok) {
    throw new Error("Failed to create chat history")
  }
  
  return response.json()
}

export async function deleteChatHistory(chatHistoryId: number): Promise<void> {
  const response = await fetch(`${API_URL}/chat-histories/${chatHistoryId}`, {
    method: "DELETE",
  })
  
  if (!response.ok) {
    throw new Error("Failed to delete chat history")
  }
}

// Message API
export async function getChatMessages(chatHistoryId: number): Promise<ChatDetail> {
  const response = await fetch(`${API_URL}/chat-histories/${chatHistoryId}/messages`)
  
  if (!response.ok) {
    throw new Error("Failed to fetch messages")
  }
  
  return response.json()
}

export async function addMessage(
  chatHistoryId: number,
  role: string,
  content: string
): Promise<Message> {
  const response = await fetch(`${API_URL}/chat-histories/${chatHistoryId}/messages`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ role, content }),
  })
  
  if (!response.ok) {
    throw new Error("Failed to add message")
  }
  
  return response.json()
}
