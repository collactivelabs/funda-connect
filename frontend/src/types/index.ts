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
  access_token: string;
  token_type: string;
  user: User;
}

// ── Teacher ───────────────────────────────────────────────────
export type VerificationStatus =
  | "pending"
  | "under_review"
  | "verified"
  | "rejected"
  | "suspended";

export type Curriculum = "CAPS" | "Cambridge" | "IEB";

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
  | "cancelled"
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
  // Nested snippets (populated on list endpoint)
  learner?: { firstName: string; lastName: string; grade: string } | null;
  subject?: { id: string; name: string } | null;
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
  subject?: string;
  curriculum?: Curriculum;
  grade?: string;
  minRate?: number;
  maxRate?: number;
  province?: string;
}
