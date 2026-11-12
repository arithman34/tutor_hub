/** Friendly names for the generated schema types the pages use. */
import type { components } from './schema'

type Schemas = components['schemas']

export type User = Schemas['User']
export type Dashboard = Schemas['Dashboard']

export type Student = Schemas['Student']
export type StudentRequest = Schemas['StudentRequest']
export type Payee = Schemas['Payee']
export type Session = Schemas['Session']

export type Conversation = Schemas['Conversation']
export type Answer = Schemas['Answer']
export type Allowance = Schemas['Allowance']
export type ChatMessage = Schemas['Message']
