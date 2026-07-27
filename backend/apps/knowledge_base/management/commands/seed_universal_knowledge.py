from django.core.management.base import BaseCommand
from django.db import transaction
from apps.knowledge_base.models import Knowledge, KnowledgeSource
from apps.knowledge_base.services.normalizer import QuestionNormalizer
from apps.knowledge_base.services.vector_store import VectorStore


class Command(BaseCommand):
    help = "Seed rich multi-crop agricultural knowledge (Wheat, Rice, Cotton, Maize, Sugarcane, Potato, Mustard, Soybean) and rebuild FAISS index."

    @transaction.atomic
    def handle(self, *args, **options):
        normalizer = QuestionNormalizer()

        source, _ = KnowledgeSource.objects.get_or_create(
            title="Universal Agriculture Knowledge Base",
            defaults={
                "source_type": KnowledgeSource.SourceType.API,
                "source_name": "Official Agriculture Package",
                "version": "2.0",
                "status": KnowledgeSource.Status.COMPLETED,
            },
        )

        KNOWLEDGE_DATA = [
            # WHEAT (गेहूं)
            {
                "crop": "Wheat",
                "category": "Irrigation",
                "subcategory": "Water Management",
                "domain": "Agronomy",
                "stage": "Growth",
                "question": "गेहूं में सिंचाई कब-कब करें?",
                "answer": "गेहूं की फसल में 5 से 6 सिंचाइयों की आवश्यकता होती है। पहली सिंचाई बुआई के 20-25 दिन बाद (CRI स्टेज) पर अवश्य करें। दूसरी सिंचाई 40-45 दिन (कल्ले निकलते समय), तीसरी 60-65 दिन (गांठ बनते समय), चौथी 80-85 दिन (फूल आते समय), और पांचवीं 100-105 दिन (दाने भरते समय) करें।",
                "keywords": "गेहूं सिंचाई पानी CRI स्टेज wheat irrigation water",
            },
            {
                "crop": "Wheat",
                "category": "Nutrient",
                "subcategory": "Fertilizer Dosage",
                "domain": "Soil Science",
                "stage": "Sowing & Growth",
                "question": "गेहूं में कितना खाद और कौन सी दवा डालें?",
                "answer": "प्रति एकड़ गेहूं के लिए 50 किग्रा DAP, 25 किग्रा पोटाश और 10 किग्रा जिंक सल्फेट बुआई के समय दें। पहली और दूसरी सिंचाई पर 45-45 किग्रा यूरिया प्रति एकड़ दें।",
                "keywords": "गेहूं खाद यूरिया DAP पोटाश जिंक wheat fertilizer urea",
            },
            {
                "crop": "Wheat",
                "category": "Disease",
                "subcategory": "Fungal Infection",
                "domain": "Plant Pathology",
                "stage": "Tillering & Heading",
                "question": "गेहूं में पीला रतुआ (Yellow Rust) रोग कैसे रोकें?",
                "answer": "गेहूं की पत्तियों पर पीली धारियां दिखने पर तुरंत प्रोपिकोनाज़ोल (Propiconazole 25% EC) 1 मिली प्रति लीटर पानी में मिलाकर स्प्रे करें। 15 दिन बाद आवश्यकतानुसार दूसरा छिड़काव करें।",
                "keywords": "गेहूं पीला रतुआ रोग रोग नियंत्रण प्रोपिकोनाज़ोल yellow rust wheat disease",
            },

            # RICE / PADDY (धान / चावल)
            {
                "crop": "Rice",
                "category": "Irrigation",
                "subcategory": "Water Management",
                "domain": "Agronomy",
                "stage": "Vegetative & Flowering",
                "question": "धान की फसल में पानी कब और कितना रखें?",
                "answer": "रोपाई के शुरुआती 2-3 सप्ताह खेत में 2-5 सेमी पानी बनाकर रखें। कल्ले निकलने के बाद और दाने भरते समय पानी की कमी न होने दें। कटाई से 10-12 दिन पहले खेत से पानी निकाल दें।",
                "keywords": "धान सिंचाई पानी रोपाई rice paddy water irrigation",
            },
            {
                "crop": "Rice",
                "category": "Pest",
                "subcategory": "Insect Control",
                "domain": "Entomology",
                "stage": "Tillering",
                "question": "धान में तना छेदक (Stem Borer) और पत्ती लपेटक की रोकथाम कैसे करें?",
                "answer": "तने छेदक के लिए कार्टैप हाइड्रोक्लोराइड (Cartap Hydrochloride 4G) 8 किग्रा प्रति एकड़ खेत में छिड़कें या क्लोरेंट्रानिलीप्रोल (Chlorantraniliprole 18.5% SC) 60 मिली प्रति एकड़ स्प्रे करें।",
                "keywords": "धान तना छेदक इल्ली कीट दवा rice stem borer pest control",
            },

            # COTTON (कपास)
            {
                "crop": "Cotton",
                "category": "Pest",
                "subcategory": "Sucking Pests",
                "domain": "Entomology",
                "stage": "Flowering & Boll Formation",
                "question": "कपास में गुलाबी इल्ली (Pink Bollworm) और चूसक कीटों का नियंत्रण कैसे करें?",
                "answer": "गुलाबी इल्ली के लिए फेरोमोन ट्रैप लगाएं। गंभीर प्रकोप में स्पिनोसैड (Spinosad 45% SC) 60 मिली या प्रोफेनोफॉस 400 मिली प्रति एकड़ 200 लीटर पानी में मिलाकर स्प्रे करें।",
                "keywords": "कपास गुलाबी इल्ली सफेद मक्खी कीड़ा cotton pink bollworm pest",
            },

            # MUSTARD (सरसों)
            {
                "crop": "Mustard",
                "category": "Pest",
                "subcategory": "Aphid Control",
                "domain": "Entomology",
                "stage": "Flowering & Pod Formation",
                "question": "सरसों में माहू (Aphid) और मोयला कीट का नियंत्रण कैसे करें?",
                "answer": "सरसों में माहू (चेपा) का प्रकोप होने पर इमडाक्लोप्रिड (Imidacloprid 17.8% SL) 50 मिली प्रति एकड़ या थायामेथोक्सम (Thiamethoxam 25% WG) 40 ग्राम प्रति एकड़ 150 लीटर पानी में मिलाकर छिड़काव करें।",
                "keywords": "सरसों माहू चेपा मोयला कीड़ा सरसों दवा mustard aphid pest",
            },

            # POTATO (आलू)
            {
                "crop": "Potato",
                "category": "Disease",
                "subcategory": "Blight Control",
                "domain": "Plant Pathology",
                "stage": "Tuber Growth",
                "question": "आलू में पछेती झुलसा (Late Blight) रोग कैसे रोकें?",
                "answer": "पत्तियों पर काले-भूरे धब्बे दिखने पर मैन्कोज़ेब (Mancozeb 75% WP) 2-2.5 ग्राम प्रति लीटर पानी में मिलाकर छिड़काव करें। गंभीर स्थिति में साइमोक्सानिल + मैन्कोज़ेब (Moximate) का स्प्रे करें।",
                "keywords": "आलू झुलसा रोग पत्ती धब्बे आलू दवा potato late blight disease",
            },

            # SUGARCANE (गन्ना)
            {
                "crop": "Sugarcane",
                "category": "Nutrient",
                "subcategory": "Fertilizer",
                "domain": "Soil Science",
                "stage": "Growth",
                "question": "गन्ने में खाद और पोषक तत्व कब और कितना दें?",
                "answer": "गन्ने में बुआई के समय 60 किग्रा DAP, 40 किग्रा पोटाश और 10 किग्रा जिंक दें। बुआई के 45 और 90 दिन बाद 50-50 किग्रा यूरिया मिट्टी चढ़ाते समय दें।",
                "keywords": "गन्ना खाद यूरिया DAP पोटाश sugarcane fertilizer dosage",
            },
        ]

        self.stdout.write("Seeding rich multi-crop knowledge records...")

        created_count = 0
        for data in KNOWLEDGE_DATA:
            norm_q = normalizer.normalize(data["question"])
            search_t = normalizer.build_search_text(
                question=data["question"],
                answer=data["answer"],
                crop=data["crop"],
                stage=data["stage"],
                domain=data["domain"],
            )

            obj, created = Knowledge.objects.get_or_create(
                question=data["question"],
                defaults={
                    "knowledge_source": source,
                    "crop": data["crop"],
                    "category": data["category"],
                    "subcategory": data["subcategory"],
                    "domain": data["domain"],
                    "stage": data["stage"],
                    "answer": data["answer"],
                    "keywords": data["keywords"],
                    "normalized_question": norm_q,
                    "search_text": search_t,
                    "is_active": True,
                },
            )
            if created:
                created_count += 1

        self.stdout.write(self.style.SUCCESS(f"Created {created_count} new multi-crop knowledge records."))

        self.stdout.write("Rebuilding FAISS index...")
        vs = VectorStore()
        vs.build_index()
        vs.save()
        self.stdout.write(self.style.SUCCESS(f"FAISS index updated with {vs.index.ntotal} vectors."))
