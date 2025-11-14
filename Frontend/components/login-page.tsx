"use client"
import { VerificationForm } from "@/components/verification-form"
import { useState } from "react"
import { Lock, CheckCircle2, Headset, MessageSquare, PhoneCall } from 'lucide-react'
import { useToast } from "@/hooks/use-toast"

const API_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000"

interface LoginPageProps {
  onLoginSuccess: (userInfo: any) => void
}

export function LoginPage({ onLoginSuccess }: LoginPageProps) {
  const [isSubmitting, setIsSubmitting] = useState(false)
  const { toast } = useToast()

  const handleVerify = async (data: { name: string; contact: string; email: string }) => {
    setIsSubmitting(true)

    try {
      const response = await fetch(`${API_URL}/test-credentials`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: data.name,
          email: data.email,
          phone_number: data.contact,
        }),
      })

      const result = await response.json()

      // Backend successfully validated the test user
      if (result.success) {
        toast({
          title: "Success",
          description: result.message || "User verified successfully!",
        })

        onLoginSuccess({
          id: result.user_id,
          name: data.name,
          email: data.email,
          phone_number: data.contact,
          contact: data.contact,
        })
        return
      }

      // Backend says NOT test user → show clear error but do NOT call validate-users
      toast({
        title: "Invalid Credentials",
        description: result.message || "These credentials do not match the test user.",
        variant: "destructive",
      })

      throw new Error(result.message || "Invalid test credentials.")
    } catch (error) {
      toast({
        title: "Error",
        description:
          error instanceof Error ? error.message : "Verification failed. Please try again.",
        variant: "destructive",
      })
    } finally {
      setIsSubmitting(false)
    }
  }

  return (
    <main className="relative min-h-screen lg:h-screen flex items-center justify-center bg-gradient-to-br from-[#f4f8ff] via-white to-[#f4f8ff] lg:overflow-hidden">

      {/* Decorative icons left */}
      <div className="hidden lg:block absolute left-12 inset-y-0 pointer-events-none">
        <div className="absolute top-[20%] w-16 h-16 rounded-full bg-gradient-to-br from-emerald-100 to-indigo-100 flex items-center justify-center transition-all duration-300 hover:scale-110 hover:shadow-lg hover:from-emerald-200 hover:to-indigo-200">
          <Headset size={32} className="text-emerald-600" />
        </div>
        <div className="absolute top-1/2 -translate-y-1/2 w-16 h-16 rounded-full bg-gradient-to-br from-emerald-100 to-indigo-100 flex items-center justify-center transition-all duration-300 hover:scale-110 hover:shadow-lg hover:from-emerald-200 hover:to-indigo-200">
          <MessageSquare size={32} className="text-indigo-600" />
        </div>
        <div className="absolute bottom-[20%] w-16 h-16 rounded-full bg-gradient-to-br from-emerald-100 to-indigo-100 flex items-center justify-center transition-all duration-300 hover:scale-110 hover:shadow-lg hover:from-emerald-200 hover:to-indigo-200">
          <PhoneCall size={32} className="text-emerald-600" />
        </div>
      </div>

      {/* Right decorative icons */}
      <div className="hidden lg:block absolute right-20 inset-y-0 pointer-events-none">
        <div className="absolute top-[20%] w-16 h-16 rounded-full bg-gradient-to-br from-emerald-100 to-indigo-100 flex items-center justify-center transition-all duration-300 hover:scale-110 hover:shadow-lg hover:from-emerald-200 hover:to-indigo-200">
          <Headset size={32} className="text-indigo-600" />
        </div>
        <div className="absolute top-1/2 -translate-y-1/2 w-16 h-16 rounded-full bg-gradient-to-br from-emerald-100 to-indigo-100 flex items-center justify-center transition-all duration-300 hover:scale-110 hover:shadow-lg hover:from-emerald-200 hover:to-indigo-200">
          <MessageSquare size={32} className="text-emerald-600" />
        </div>
        <div className="absolute bottom-[20%] w-16 h-16 rounded-full bg-gradient-to-br from-emerald-100 to-indigo-100 flex items-center justify-center transition-all duration-300 hover:scale-110 hover:shadow-lg hover:from-emerald-200 hover:to-indigo-200">
          <PhoneCall size={32} className="text-indigo-600" />
        </div>
      </div>

      {/* Content */}
      <div className="w-full h-full max-w-7xl mx-auto px-4">
        {/* Desktop layout */}
        <div className="hidden lg:grid lg:grid-cols-2 lg:gap-12 lg:items-stretch lg:min-h-screen">

          <div className="flex items-center justify-center h-full overflow-hidden rounded-2xl border-2 border-gray-200 shadow-lg">
            <img src="/customer-support-agent.png" alt="Smart Support verification" className="w-full h-full object-cover" />
          </div>

          <div className="flex flex-col justify-between h-full py-8">
            <div className="space-y-6">

              <div className="flex items-start gap-4">
                <div className="relative p-[2px] w-14 h-14 rounded-full bg-gradient-to-br from-emerald-500/60 to-indigo-500/60 shadow-md">
                  <div className="flex items-center justify-center w-full h-full rounded-full bg-white/80 backdrop-blur">
                    <Lock className="w-6 h-6 text-emerald-700" />
                  </div>
                </div>

                <div className="space-y-3">
                  <h1 className="text-4xl font-extrabold tracking-tight bg-gradient-to-r from-emerald-700 to-indigo-700 bg-clip-text text-transparent">
                    Verify Your Identity
                  </h1>
                  <p className="text-base text-gray-600 max-w-md">
                    We're here to assist you and ensure you get the right solution as quickly as possible.
                  </p>
                </div>
              </div>
            </div>

            {/* Form */}
            <VerificationForm onSubmit={handleVerify} isLoading={isSubmitting} />

            <div className="space-y-4 pt-4">
              <div className="flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                <span className="text-sm text-gray-600">Your information is secure and encrypted</span>
              </div>
              <div className="flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                <span className="text-sm text-gray-600">Fast and seamless verification process</span>
              </div>
              <div className="flex items-start gap-3">
                <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
                <span className="text-sm text-gray-600">24/7 support available for assistance</span>
              </div>
            </div>
          </div>
        </div>

        {/* Mobile layout */}
        <div className="lg:hidden flex flex-col gap-8 py-8">
          <div className="space-y-4">
            <div className="relative p-[2px] w-12 h-12 rounded-full bg-gradient-to-br from-emerald-500/60 to-indigo-500/60 shadow-sm inline-flex">
              <div className="flex items-center justify-center w-full h-full rounded-full bg-white/85 backdrop-blur">
                <Lock className="w-5 h-5 text-emerald-700" />
              </div>
            </div>

            <h1 className="text-3xl font-extrabold tracking-tight bg-gradient-to-r from-emerald-700 to-indigo-700 bg-clip-text text-transparent">
              Verify Your Identity
            </h1>
            <p className="text-sm text-gray-600">We're here to assist you and ensure fast help.</p>
          </div>

          <div className="aspect-video bg-gray-100 rounded-2xl border-2 border-gray-200 overflow-hidden">
            <img src="/customer-support-agent.png" className="w-full h-full object-cover" />
          </div>

          <VerificationForm onSubmit={handleVerify} isLoading={isSubmitting} />

          <div className="space-y-3 pb-4">
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
              <span className="text-sm text-gray-600">Your information is secure and encrypted</span>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
              <span className="text-sm text-gray-600">Fast and seamless verification process</span>
            </div>
            <div className="flex items-start gap-3">
              <CheckCircle2 className="w-5 h-5 text-emerald-600 flex-shrink-0" />
              <span className="text-sm text-gray-600">24/7 support available for assistance</span>
            </div>
          </div>
        </div>
      </div>
    </main>
  )
}