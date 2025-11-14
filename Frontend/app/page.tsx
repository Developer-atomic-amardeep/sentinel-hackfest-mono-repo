"use client"

import { LoginPage } from "@/components/login-page"
import { ChatbotPage } from "@/components/chatbot-page"
import { useState } from "react"

export default function Home() {
  const [isLoggedIn, setIsLoggedIn] = useState(false)
  const [userInfo, setUserInfo] = useState(null)

  const handleLoginSuccess = (info: any) => {
    setUserInfo(info)
    setIsLoggedIn(true)
  }

  const handleLogout = () => {
    setIsLoggedIn(false)
    setUserInfo(null)
  }

  return (
    <>
      {!isLoggedIn ? (
        <LoginPage onLoginSuccess={handleLoginSuccess} />
      ) : (
        <ChatbotPage userInfo={userInfo} onLogout={handleLogout} />
      )}
    </>
  )
}
