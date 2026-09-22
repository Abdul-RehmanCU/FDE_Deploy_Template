declare global {
  interface Window {
    __FDE_CONFIG__?: {
      brandName?: string
    }
  }
}

const configuredBrand = window.__FDE_CONFIG__?.brandName?.trim()

export const brandName = configuredBrand || "FDE Deploy"
