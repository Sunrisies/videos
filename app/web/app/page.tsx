import VideosPage from '@/components/videos'
import { Suspense } from 'react'
export default function Home() {
  return (
    <Suspense fallback={<div>Loading videos...</div>}>
      <VideosPage />
    </Suspense>
  )
}