import html2canvas from 'html2canvas'
import { jsPDF } from 'jspdf'

export const exportToPDF = async (elementId, filename = 'Procurement_Executive_Summary.pdf') => {
  const element = document.getElementById(elementId)
  if (!element) return

  try {
    const canvas = await html2canvas(element, {
      scale: 2,
      useCORS: true,
      backgroundColor: '#020617', // Match dashboard slate-950
      logging: false,
    })

    const imgData = canvas.toDataURL('image/png')
    const pdf = new jsPDF({
      orientation: 'portrait',
      unit: 'px',
      format: [canvas.width / 2, canvas.height / 2],
    })

    pdf.addImage(imgData, 'PNG', 0, 0, canvas.width / 2, canvas.height / 2)
    pdf.save(filename)
  } catch (err) {
    console.error('PDF Export failed:', err)
    alert('Failed to generate PDF. Please try again.')
  }
}
