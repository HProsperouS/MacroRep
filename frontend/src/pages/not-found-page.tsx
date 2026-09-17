import { Link } from "react-router-dom"

import { PageHeader } from "@/components/layout/page-header"

export default function NotFoundPage() {
  return (
    <>
      <PageHeader title="Page not found" />
      <Link to="/" className="text-primary">
        Back to Home
      </Link>
    </>
  )
}
