/* ============================================================================
   Clinic Management Lite - white-label configuration (web edition)
   ----------------------------------------------------------------------------
   Edit this file for each customer deployment. Nothing else needs to change.
   Values here are the defaults for a fresh browser; the administrator can still
   change the clinic profile, logo, footers and language from Settings inside
   the app (those values are stored in the browser's IndexedDB).
   ============================================================================ */
window.CML_CONFIG = {
  // Product identity shown in the browser tab, the login screen and the About section
  productName: "Clinic Management Lite",
  version: "1.0.0",

  // Your company (the reseller). Shown in Settings > About.
  vendor: {
    name: "",            // e.g. "Techxant"
    phone: "",           // e.g. "0300-1234567"
    website: "",         // e.g. "https://example.com"
    supportEmail: "",    // e.g. "support@example.com"
  },

  // Storage namespace: change per customer when several clinics share one browser or device.
  storageKey: "cml",

  // Clinic defaults applied to a fresh database (the administrator can edit them in Settings)
  clinic: {
    name: "City Care Clinic",
    tagline: "Family Medicine and General Practice",
    address: "12-B Main Boulevard, Gulberg III, Lahore",
    phone: "042-35761234",
    email: "info@citycareclinic.pk",
    logo: "",                          // data URL or a path such as "assets/logo.svg"; "" = default mark
    currencySymbol: "Rs.",
    language: "en",                    // "en" or "ur"
    appointmentDuration: 15,           // minutes per slot
    defaultConsultationFee: 1500,
    tokenPrefix: "T",
    paperSize: "A5",                   // A4, A5 or A6 for prescriptions and receipts
    rxFooterEn: "Please bring this prescription on your next visit.",
    rxFooterUr: "براہ کرم اگلی ملاقات پر یہ نسخہ ساتھ لائیں۔",
    receiptFooterEn: "Thank you for choosing our clinic. Fees once paid are non-refundable.",
    receiptFooterUr: "ہمارے کلینک کا انتخاب کرنے کا شکریہ۔ ادا شدہ فیس ناقابل واپسی ہے۔",
    lowStockThreshold: 10,
    expiryWarningDays: 90,
    maxDiscountWithoutAuth: 0,
    followUpWindowDays: 7,
  },

  // Theme tokens (teal / navy / light). Change here to re-brand without touching the CSS.
  theme: {
    primary: "#087F8C",
    primaryDark: "#066670",
    navy: "#173B48",
    background: "#F3F7F8",
  },

  // Feature switches: turn modules off for cheaper plans
  features: {
    urdu: true,
    demoData: true,      // seed synthetic demo data on first launch and show demo accounts on the login screen
    inventory: true,
    reports: true,
    backup: true,
  },

  // Optional licence notice shown in Settings > About (purely informational)
  licence: {
    plan: "Prototype",
    licensedTo: "",
    expires: "",
  },
};
