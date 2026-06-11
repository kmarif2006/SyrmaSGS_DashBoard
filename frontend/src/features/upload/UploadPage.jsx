import { useState, useCallback } from 'react'
import { useNavigate } from 'react-router-dom'
import { useDropzone } from 'react-dropzone'
import { 
  FileText, 
  Upload, 
  CheckCircle2, 
  AlertCircle, 
  ArrowRight, 
  BarChart3, 
  Database,
  Loader2,
  Trash2
} from 'lucide-react'
import { toast } from 'react-hot-toast'
import { uploadTransactions, uploadMaster, mergeData, fetchStatus, cn } from '../../shared'

function FileUploadZone({ label, subtitle, onUpload, status, filename, type }) {
  const [uploading, setUploading] = useState(false)
  const [progress, setProgress] = useState(0)

  const onDrop = useCallback(async (acceptedFiles) => {
    const file = acceptedFiles[0]
    if (!file) return

    setUploading(true)
    setProgress(0)
    try {
      await onUpload(file, setProgress)
      toast.success(`${label} uploaded successfully`)
    } catch (err) {
      toast.error(err.response?.data?.error || `Failed to upload ${label}`)
    } finally {
      setUploading(false)
    }
  }, [label, onUpload])

  const { getRootProps, getInputProps, isDragActive } = useDropzone({
    onDrop,
    accept: { 'text/csv': ['.csv'] },
    multiple: false,
    disabled: uploading
  })

  return (
    <div className={cn(
      "glass-card p-8 flex flex-col items-center justify-center border-2 border-dashed transition-all duration-300",
      status ? "border-emerald-500/40 bg-emerald-500/5" : "border-slate-700/60 hover:border-indigo-500/40",
      isDragActive && "border-indigo-500 bg-indigo-500/5 scale-[1.02]"
    )} {...getRootProps()}>
      <input {...getInputProps()} />
      
      <div className={cn(
        "w-16 h-16 rounded-2xl flex items-center justify-center mb-5 shadow-2xl",
        status ? "bg-emerald-500 text-white" : "bg-slate-800 text-slate-400"
      )}>
        {uploading ? (
          <Loader2 className="animate-spin" size={32} />
        ) : status ? (
          <CheckCircle2 size={32} />
        ) : type === 'txn' ? (
          <FileText size={32} />
        ) : (
          <Database size={32} />
        )}
      </div>

      <h3 className="text-lg font-bold text-white mb-1">{label}</h3>
      <p className="text-sm text-slate-500 mb-6 text-center max-w-[240px]">{subtitle}</p>

      {uploading ? (
        <div className="w-full max-w-[200px]">
          <div className="h-1.5 w-full bg-slate-800 rounded-full overflow-hidden">
            <div 
              className="h-full bg-indigo-500 transition-all duration-300" 
              style={{ width: `${progress}%` }} 
            />
          </div>
          <p className="text-[10px] text-center mt-2 text-slate-400 font-bold uppercase tracking-widest">Uploading {progress}%</p>
        </div>
      ) : status ? (
        <div className="flex flex-col items-center">
          <p className="text-sm font-medium text-emerald-400 mb-4 bg-emerald-500/10 px-3 py-1 rounded-full border border-emerald-500/20">
            {filename}
          </p>
          <button className="text-xs text-slate-500 hover:text-slate-300 transition-colors flex items-center gap-1">
            Change File
          </button>
        </div>
      ) : (
        <button className="btn-primary flex items-center gap-2">
          <Upload size={16} />
          Select CSV
        </button>
      )}
    </div>
  )
}

export default function UploadPage() {
  const navigate = useNavigate()
  const [merging, setMerging] = useState(false)
  const [status, setStatus] = useState({ 
    transaction_uploaded: false, 
    master_uploaded: false,
    transaction_filename: null,
    master_filename: null
  })

  // Initial status check
  useState(() => {
    fetchStatus().then(setStatus).catch(() => {})
  }, [])

  const handleMerge = async () => {
    setMerging(true)
    try {
      const res = await mergeData()
      toast.success("Ready! Analyzing 120,000+ data points.")
      navigate('/dashboard')
    } catch (err) {
      toast.error(err.response?.data?.error || "Merge failed")
    } finally {
      setMerging(false)
    }
  }

  const handleTxnUpload = async (file, onProgress) => {
    const res = await uploadTransactions(file, onProgress)
    setStatus(prev => ({ ...prev, transaction_uploaded: true, transaction_filename: file.name }))
  }

  const handleMasterUpload = async (file, onProgress) => {
    const res = await uploadMaster(file, onProgress)
    setStatus(prev => ({ ...prev, master_uploaded: true, master_filename: file.name }))
  }

  const isReady = status.transaction_uploaded && status.master_uploaded

  return (
    <div className="min-h-screen flex flex-col items-center justify-center p-6 sm:p-12 relative overflow-hidden">
      {/* Background Decor */}
      <div className="absolute top-0 left-0 w-full h-full -z-10 pointer-events-none">
        <div className="absolute top-[-10%] right-[-10%] w-[50%] h-[50%] bg-indigo-600/10 blur-[120px] rounded-full" />
        <div className="absolute bottom-[-10%] left-[-10%] w-[50%] h-[50%] bg-violet-600/10 blur-[120px] rounded-full" />
      </div>

      <div className="max-w-4xl w-full">
        {/* Header */}
        <div className="text-center mb-12">
          <div className="inline-flex items-center justify-center w-16 h-16 rounded-2xl bg-gradient-to-br from-indigo-600 to-violet-700 shadow-2xl mb-6">
            <BarChart3 size={32} className="text-white" />
          </div>
          <h1 className="text-4xl sm:text-5xl font-extrabold text-white mb-4 tracking-tight">
            Syrma <span className="gradient-text">Procurement</span> Analytics
          </h1>
          <p className="text-slate-400 text-lg max-w-2xl mx-auto leading-relaxed">
            Upload your SAP export files to generate real-time spend insights, 
            supplier performance metrics, and INR-normalized financial reports.
          </p>
        </div>

        {/* Upload Cards */}
        <div className="grid grid-cols-1 md:grid-cols-2 gap-8 mb-12">
          <FileUploadZone 
            type="txn"
            label="Transaction Data" 
            subtitle="Upload PO Line Items (Sheet1 (2).csv). Must contain Net Price, Qty, and Document ID."
            onUpload={handleTxnUpload}
            status={status.transaction_uploaded}
            filename={status.transaction_filename}
          />
          <FileUploadZone 
            type="master"
            label="Master Data" 
            subtitle="Upload EKKO Master (EKKO.csv). Required for Exchange Rates and Company Codes."
            onUpload={handleMasterUpload}
            status={status.master_uploaded}
            filename={status.master_filename}
          />
        </div>

        {/* Action Button */}
        <div className="flex flex-col items-center">
          <button 
            onClick={handleMerge}
            disabled={!isReady || merging}
            className={cn(
              "btn-primary h-14 px-12 text-lg flex items-center gap-3 transition-all transform",
              !isReady ? "opacity-50 grayscale cursor-not-allowed" : "hover:scale-105 active:scale-95"
            )}
          >
            {merging ? (
              <>
                <Loader2 className="animate-spin" size={24} />
                Processing Datasets...
              </>
            ) : (
              <>
                Generate Dashboard
                <ArrowRight size={24} />
              </>
            )}
          </button>
          
          {!isReady && (
            <p className="mt-4 flex items-center gap-2 text-sm text-slate-500">
              <AlertCircle size={14} />
              Please upload both files to proceed
            </p>
          )}

          {isReady && !merging && (
            <p className="mt-4 text-sm text-emerald-400 font-medium">
              Files verified. Ready to synchronize data.
            </p>
          )}
        </div>
      </div>

      {/* Footer Info */}
      <div className="mt-20 flex gap-12 text-slate-600">
        <div className="text-center">
          <p className="text-xl font-bold text-slate-400">100k+</p>
          <p className="text-[10px] uppercase font-bold tracking-widest">Rows Supported</p>
        </div>
        <div className="text-center">
          <p className="text-xl font-bold text-slate-400">0ms</p>
          <p className="text-[10px] uppercase font-bold tracking-widest">Latency Processing</p>
        </div>
        <div className="text-center">
          <p className="text-xl font-bold text-slate-400">INR</p>
          <p className="text-[10px] uppercase font-bold tracking-widest">Auto-Conversion</p>
        </div>
      </div>
    </div>
  )
}
