from gentle import diff_align
from gentle import kaldi_queue
from gentle import language_model
from gentle import metasentence
from gentle import multipass
from gentle.transcription import MultiThreadedTranscriber

class ForcedAligner():

    def __init__(self, resources, transcript, nthreads=4, **kwargs):
        self.kwargs = kwargs
        self.nthreads = nthreads
        self.transcript = transcript
        self.ms = metasentence.MetaSentence(transcript, resources.vocab)
        ks = self.ms.get_kaldi_sequence()
        gen_hclg_filename = language_model.make_bigram_language_model(ks, resources.proto_langdir, **kwargs)
        self.queue = kaldi_queue.build(resources, hclg_path=gen_hclg_filename, nthreads=nthreads)
        self.mtt = MultiThreadedTranscriber(self.queue, nthreads=nthreads)

    def transcribe(self, wavfile, progress_cb=None, logging=None):
        words = self.mtt.transcribe(wavfile, progress_cb=progress_cb)

        # Clear queue (would this be gc'ed?)
        for i in range(self.nthreads):
            k = self.queue.get()
            k.stop()

        # Align words
        output = {}
        output['words'] = diff_align.align(words, self.ms, **self.kwargs)
        output['transcript'] = self.transcript

        # Perform a second-pass with unaligned words
        if logging is not None:
            logging.info("%d unaligned words (of %d)" % (len([X for X in output['words'] if X.get("case") == "not-found-in-audio"]), len(output['words'])))

        if progress_cb is not None:
            progress_cb({'status': 'ALIGNING'})

        output['words'] = multipass.realign(wavfile, output['words'], self.ms, nthreads=self.nthreads, progress_cb=progress_cb)

        if logging is not None:
            logging.info("after 2nd pass: %d unaligned words (of %d)" % (len([X for X in output['words'] if X.get("case") == "not-found-in-audio"]), len(output['words'])))

        return output
