import { HashRouter, Routes, Route } from 'react-router-dom'
import Layout from './components/Layout'
import Home from './pages/Home'
import Books from './pages/Books'
import Runs from './pages/Runs'
import Explorer from './pages/Explorer'
import Archive from './pages/Archive'
import Universe from './pages/Universe'

export default function App() {
  return (
    <HashRouter>
      <Layout>
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/books" element={<Books />} />
          <Route path="/runs" element={<Runs />} />
          <Route path="/universe" element={<Universe />} />
          <Route path="/explorer" element={<Explorer />} />
          <Route path="/archive" element={<Archive />} />
        </Routes>
      </Layout>
    </HashRouter>
  )
}
