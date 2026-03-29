// ── Auth ─────────────────────────────────────────────────────
export type UserRole = "teacher" | "parent" | "admin";

export interface User {
  id: string;
  email: string;
  firstName: string;
  lastName: string;
  role: UserRole;
  avatarUrl?: string;
  emailVerified: boolean;
}

export interface AuthTokens {
  accessToken: string;
}

export interface AuthResponse {
  accessToken: string;
  token_type: string;
  user: User;
}

export interface GoogleOAuthStartResponse {
  authorizationUrl: string;
}

export interface AuthSession {
  id: string;
  current: boolean;
  createdAt: string;
  lastSeenAt: string;
  expiresAt: string;
  userAgent?: string | null;
  ipAddress?: string | null;
}

export interface ConsentState {
  granted: boolean;
  version: string;
  grantedAt?: string | null;
  revokedAt?: string | null;
}

export interface AccountConsent {
  termsOfService: ConsentState;
  privacyPolicy: ConsentState;
  marketingEmail: ConsentState;
  marketingSms: ConsentState;
}

export interface AccountDeletionStatus {
  status: "active" | "pendingDeletion" | "anonymized";
  isActive: boolean;
  deletionRequestedAt?: string | null;
  deletionScheduledFor?: string | null;
  anonymizedAt?: string | null;
  cancelledFutureBookings: number;
  gracePeriodDays: number;
}

export interface AccountDataExportResponse {
  exportedAt: string;
  data: Record<string, unknown>;
}

export interface NotificationItem {
  id: string;
  type: string;
  channel: string;
  title: string;
  body: string;
  metadata?: Record<string, unknown> | null;
  isRead: boolean;
  sentAt: string;
  readAt?: string | null;
  createdAt: string;
}

export interface NotificationListResponse {
  items: NotificationItem[];
  unreadCount: number;
}

export interface NotificationPreferences {
  inAppEnabled: boolean;
  emailEnabled: boolean;
  smsEnabled: boolean;
  pushEnabled: boolean;
}

export interface CurriculumOption {
  code: Curriculum;
  label: string;
  description: string;
}

export interface GradeLevelOption {
  value: string;
  label: string;
  order: number;
}

export interface GradeLevelGroup {
  phase: string;
  items: GradeLevelOption[];
}

export interface TopicReference {
  id: string;
  subject: string;
  subjectName: string;
  grade: string;
  curriculum: Curriculum;
  term?: number | null;
  name: string;
  referenceCode?: string | null;
}

// ── Teacher ───────────────────────────────────────────────────
export type VerificationStatus =
  | "pending"
  | "under_review"
  | "verified"
  | "rejected"
  | "suspended";

export type Curriculum = "CAPS" | "Cambridge" | "IEB";
export type VerificationDocumentType =
  | "id_document"
  | "qualification"
  | "sace_certificate"
  | "nrso_clearance"
  | "reference_letter";
export type VerificationDocumentStatus = "pending" | "approved" | "rejected";

export interface TeacherProfile {
  id: string;
  userId: string;
  bio?: string;
  headline?: string;
  yearsExperience?: number;
  hourlyRateCents?: number;
  curricula: Curriculum[];
  verificationStatus: VerificationStatus;
  isListed: boolean;
  averageRating?: number;
  totalReviews: number;
  totalLessons: number;
  isPremium: boolean;
  province?: string;
  subjects: TeacherSubject[];
  user: Pick<User, "firstName" | "lastName" | "avatarUrl">;
}

export interface TeacherSubject {
  id: string;
  subjectId: string;
  subjectName: string;
  gradeLevels: string[];
  curriculum: Curriculum;
}

export interface VerificationDocument {
  id: string;
  documentType: VerificationDocumentType;
  fileUrl: string;
  fileName: string;
  status: VerificationDocumentStatus;
  createdAt: string;
  reviewerNotes?: string | null;
  reviewedAt?: string | null;
}

// ── Parent & Learner ──────────────────────────────────────────
export interface Learner {
  id: string;
  parentId: string;
  firstName: string;
  lastName: string;
  grade: string;
  curriculum: Curriculum;
  notes?: string;
  age?: number;
}

export type PaymentStatus =
  | "pending"
  | "complete"
  | "failed"
  | "refunded"
  | "partially_refunded"
  | "cancelled";

export interface ParentPaymentHistoryItem {
  id: string;
  bookingId: string;
  gateway: string;
  gatewayPaymentId?: string | null;
  amountCents: number;
  status: PaymentStatus;
  paidAt?: string | null;
  createdAt: string;
  bookingStatus: BookingStatus;
  scheduledAt: string;
  teacherName: string;
  learnerName: string;
  subjectName: string;
  refundAmountCents: number;
  refundStatus?: "pending" | "processing" | "refunded" | "failed" | "cancelled" | null;
  refundRequestedAt?: string | null;
  refundProcessedAt?: string | null;
  isSeries: boolean;
  seriesLessons: number;
}

export interface ParentPaymentHistorySummary {
  completedPaymentsCents: number;
  pendingPaymentsCents: number;
  refundedPaymentsCents: number;
  refundPendingCents: number;
  payments: ParentPaymentHistoryItem[];
}

export interface ParentPaymentReceipt {
  paymentId: string;
  bookingId: string;
  receiptReference: string;
  issuedAt: string;
  paymentStatus: PaymentStatus;
  paymentGateway: string;
  paymentGatewayReference?: string | null;
  amountCents: number;
  refundAmountCents: number;
  netPaidCents: number;
  parentName: string;
  parentEmail: string;
  teacherName: string;
  learnerName: string;
  subjectName: string;
  scheduledAt: string;
  durationMinutes: number;
  isTrial: boolean;
  isSeries: boolean;
  seriesLessons: number;
}

export interface LearnerSubjectProgress {
  subjectId: string;
  subjectName: string;
  completedLessons: number;
  totalMinutes: number;
  latestLessonAt?: string | null;
}

export interface LearnerLessonProgress {
  bookingId: string;
  scheduledAt: string;
  durationMinutes: number;
  status: BookingStatus;
  subjectName: string;
  teacherName: string;
  lessonNotes?: string | null;
  topicsCovered: TopicReference[];
}

export interface LearnerProgress {
  learnerId: string;
  learnerName: string;
  grade: string;
  curriculum: Curriculum;
  completedLessons: number;
  upcomingLessons: number;
  totalMinutes: number;
  subjectCount: number;
  topicCount: number;
  lastCompletedAt?: string | null;
  subjects: LearnerSubjectProgress[];
  topicsCovered: TopicReference[];
  recentLessons: LearnerLessonProgress[];
}

export interface LearnerReport extends LearnerProgress {
  reportReference: string;
  generatedAt: string;
}

// ── Subjects ──────────────────────────────────────────────────
export interface Subject {
  id: string;
  name: string;
  slug: string;
  tier: 1 | 2 | 3 | 4;
  icon?: string;
}

// ── Booking ───────────────────────────────────────────────────
export type BookingStatus =
  | "pending_payment"
  | "confirmed"
  | "in_progress"
  | "completed"
  | "disputed"
  | "cancelled"
  | "expired"
  | "reviewed";

export interface Booking {
  id: string;
  parentId: string;
  teacherId: string;
  learnerId: string;
  subjectId: string;
  scheduledAt: string; // ISO 8601
  durationMinutes: number;
  status: BookingStatus;
  amountCents: number;
  commissionCents: number;
  teacherPayoutCents: number;
  videoRoomUrl?: string;
  isTrial: boolean;
  isRecurring: boolean;
  recurringBookingId?: string | null;
  lessonNotes?: string | null;
  topicsCovered?: string[];
  // Nested snippets (populated on list endpoint)
  learner?: { id: string; firstName: string; lastName: string; grade: string; curriculum: Curriculum } | null;
  subject?: { id: string; name: string; slug: string } | null;
}

export interface BookableSlot {
  startAt: string;
  endAt: string;
  date: string;
  dateLabel: string;
  timeLabel: string;
}

// ── Reviews ───────────────────────────────────────────────────
export interface Review {
  id: string;
  bookingId: string;
  teacherId: string;
  parentId: string;
  rating: 1 | 2 | 3 | 4 | 5;
  comment?: string;
  teacherReply?: string;
  createdAt: string;
}

// ── API ───────────────────────────────────────────────────────
export interface PaginatedResponse<T> {
  items: T[];
  total: number;
  page: number;
  pageSize: number;
  totalPages: number;
}

export interface ApiError {
  detail: string;
  code?: string;
}

// ── Availability ──────────────────────────────────────────────
export interface AvailabilitySlot {
  id: string;
  dayOfWeek: number; // 0=Mon … 6=Sun
  startTime: string; // "HH:MM"
  endTime: string;
  isActive: boolean;
}

// ── Search / Filter ───────────────────────────────────────────
export interface TeacherSearchParams {
  q?: string;
  subject?: string;
  curriculum?: Curriculum;
  grade?: string;
  minRate?: number;
  maxRate?: number;
  minRating?: number;
  province?: string;
  sortBy?: "rating_average" | "hourly_rate_cents" | "total_lessons" | "created_at";
  sortOrder?: "asc" | "desc";
}
