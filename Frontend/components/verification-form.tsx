"use client"

import { useState } from "react"
import { useForm } from "react-hook-form"
import { zodResolver } from "@hookform/resolvers/zod"
import * as z from "zod"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Loader2 } from 'lucide-react'

const verificationSchema = z.object({
  name: z
    .string()
    .min(2, "Name must be at least 2 characters")
    .max(60, "Name must be at most 60 characters")
    .regex(/^[a-zA-Z\s]+$/, "Name can only contain letters and spaces")
    .trim(),
  contact: z
    .string()
    .regex(/^(\+91)?[6-9]\d{9}$/, "Please enter a valid Indian mobile number (10 digits or +91 prefixed)")
    .trim(),
  email: z.string().email("Please enter a valid email address").trim(),
})

type VerificationFormData = z.infer<typeof verificationSchema>

interface VerificationFormProps {
  onSubmit: (data: VerificationFormData) => Promise<void>
  isLoading?: boolean
}

export function VerificationForm({ onSubmit, isLoading = false }: VerificationFormProps) {
  const [submitError, setSubmitError] = useState<string | null>(null)

  const {
    register,
    handleSubmit,
    formState: { errors, isSubmitting },
    reset,
  } = useForm<VerificationFormData>({
    resolver: zodResolver(verificationSchema),
    mode: "onBlur",
  })

  const isProcessing = isSubmitting || isLoading

  const onFormSubmit = async (data: VerificationFormData) => {
    setSubmitError(null)
    try {
      await onSubmit(data)
      reset()
    } catch (error) {
      setSubmitError(error instanceof Error ? error.message : "Verification failed. Please try again.")
    }
  }

  return (
    <form onSubmit={handleSubmit(onFormSubmit)} className="space-y-6" noValidate autoComplete="off">
      <div className="bg-white/90 backdrop-blur rounded-2xl border border-gray-200 p-6 shadow-md space-y-5">
        {/* Name Field */}
        <div className="space-y-2">
          <label htmlFor="name" className="text-sm font-medium text-gray-700">
            Name
          </label>
          <Input
            id="name"
            type="text"
            placeholder="Enter your full name"
            {...register("name")}
            disabled={isProcessing}
            autoComplete="off"
            spellCheck={false}
            className="rounded-lg focus-visible:ring-2 focus-visible:ring-emerald-300 focus-visible:border-emerald-400 transition"
            aria-invalid={!!errors.name}
            aria-describedby={errors.name ? "name-error" : undefined}
          />
          {errors.name && (
            <p id="name-error" className="text-sm text-red-600 mt-1" role="alert">
              {errors.name.message}
            </p>
          )}
        </div>

        {/* Contact Number Field */}
        <div className="space-y-2">
          <label htmlFor="contact" className="text-sm font-medium text-gray-700">
            Contact No.
          </label>
          <Input
            id="contact"
            type="tel"
            placeholder="10-digit mobile or +91 format"
            {...register("contact")}
            disabled={isProcessing}
            autoComplete="off"
            spellCheck={false}
            className="rounded-lg focus-visible:ring-2 focus-visible:ring-emerald-300 focus-visible:border-emerald-400 transition"
            aria-invalid={!!errors.contact}
            aria-describedby={errors.contact ? "contact-error" : undefined}
          />
          {errors.contact && (
            <p id="contact-error" className="text-sm text-red-600 mt-1" role="alert">
              {errors.contact.message}
            </p>
          )}
        </div>

        {/* Email Field */}
        <div className="space-y-2">
          <label htmlFor="email" className="text-sm font-medium text-gray-700">
            Email Id
          </label>
          <Input
            id="email"
            type="email"
            placeholder="Enter your email address"
            {...register("email")}
            disabled={isProcessing}
            autoComplete="off"
            spellCheck={false}
            className="rounded-lg focus-visible:ring-2 focus-visible:ring-emerald-300 focus-visible:border-emerald-400 transition"
            aria-invalid={!!errors.email}
            aria-describedby={errors.email ? "email-error" : undefined}
          />
          {errors.email && (
            <p id="email-error" className="text-sm text-red-600 mt-1" role="alert">
              {errors.email.message}
            </p>
          )}
        </div>

        {/* Submit Error Banner */}
        {submitError && (
          <div className="p-3 bg-red-50 border border-red-200 rounded-lg text-sm text-red-600" role="alert">
            {submitError}
          </div>
        )}
      </div>

      {/* Verify Button */}
      <Button
        type="submit"
        disabled={isProcessing}
        className="w-full py-6 text-base font-medium rounded-2xl transition-all bg-emerald-600 hover:bg-emerald-700 text-white"
      >
        {isProcessing ? (
          <>
            <Loader2 className="mr-2 h-4 w-4 animate-spin" />
            Verifying...
          </>
        ) : (
          "Verify"
        )}
      </Button>
    </form>
  )
}
