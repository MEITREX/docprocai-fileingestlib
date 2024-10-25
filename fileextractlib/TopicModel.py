import logging
import time

import numpy as np
import psycopg
from bertopic import BERTopic
from bertopic.representation import MaximalMarginalRelevance
from bertopic.vectorizers import ClassTfidfTransformer
from sklearn.feature_extraction.text import CountVectorizer

from persistence.MediaRecordInfoDbConnector import MediaRecordInfoDbConnector
from persistence.SegmentDbConnector import SegmentDbConnector
from persistence.entities import DocumentSegmentEntity, VideoSegmentEntity, AssessmentSegmentEntity

_logger = logging.getLogger(__name__)


class TopicModel:
    model = BERTopic()

    def __init__(self, record_segments: list[VideoSegmentEntity| DocumentSegmentEntity| AssessmentSegmentEntity]):
        self.record_segments = []
        self.docs = []
        self.record_segments = record_segments
        self.docs = []

    def create_topic_model(self):
        embeddings = []

        for entity in self.record_segments:
            if isinstance(entity, DocumentSegmentEntity):
                self.docs.append(entity.text)
                embeddings.append(entity.embedding)
            if isinstance(entity, VideoSegmentEntity):
                self.docs.append(entity.transcript)
                embeddings.append(entity.embedding)
            if isinstance(entity, AssessmentSegmentEntity):
                self.docs.append(entity.textual_representation)
                embeddings.append(entity.embedding)

        if len(self.docs) < 11:
            _logger.info("More documents needed to create topic model.")
            return

        embeddings = np.array(embeddings)
        vectorizer_model = CountVectorizer(stop_words="english", ngram_range=(1, 3))
        ctfidf_model = ClassTfidfTransformer(reduce_frequent_words=True, bm25_weighting=True)
        mmr = MaximalMarginalRelevance(diversity=0.3)

        representation_models = mmr

        self.model = BERTopic(
            min_topic_size=7,
            vectorizer_model=vectorizer_model,
            ctfidf_model=ctfidf_model,
            representation_model=representation_models
        )

        self.model.fit_transform(self.docs, embeddings)

    def add_tags_to_media_records(self, segments, media_records):
        if len(self.docs) < 11:
            _logger.info("Topic model wasn't created. More documents needed.")
            return
        document_info = self.model.get_document_info(self.docs)
        mediarecords_with_tags = {}

        i = 0
        for record in media_records:
            mediarecords_with_tags.update({record.get(id): set()})

        while i < len(segments):
            if isinstance(segments[i], AssessmentSegmentEntity):
                i += 1
                continue

            mediarecord_id = segments[i].media_record_id


            if isinstance(segments[i], DocumentSegmentEntity):
                if segments[i].text != document_info['Document'].iat[i]:
                    i += 1
                    continue
            elif isinstance(segments[i], VideoSegmentEntity):
                if segments[i].transcript != document_info['Document'].iat[i]:
                    i += 1
                    continue

            tags = set()
            if mediarecords_with_tags.get(mediarecord_id) is not None:
                tags = mediarecords_with_tags.get(mediarecord_id)
            tags.update(set(document_info['Representation'].iat[i]))

            mediarecords_with_tags.update({mediarecord_id: tags})
            i += 1

        return mediarecords_with_tags

    def add_tags_to_assessments(self, segments, assesments):
        if len(self.docs) < 11:
            _logger.info("Topic model wasn't created. More documents needed.")
            return
        document_info = self.model.get_document_info(self.docs)
        assesments_with_tags = {}

        i = 0
        for assessment in assesments:
            assesments_with_tags.update({assessment.get(id): set()})

        while i < len(segments):
            if isinstance(segments[i], DocumentSegmentEntity) or isinstance(segments[i], VideoSegmentEntity):
                i += 1
                continue

            assessment_id = segments[i].assessment_id

            if isinstance(segments[i], AssessmentSegmentEntity):
                if segments[i].textual_representation != document_info['Document'].iat[i]:
                    i += 1
                    continue

            tags = set()
            if assesments_with_tags.get(assessment_id) is not None:
                tags = assesments_with_tags.get(assessment_id)
            tags.update(set(document_info['Representation'].iat[i]))

            assesments_with_tags.update({assessment_id: tags})
            i += 1

        return assesments_with_tags


if __name__ == "__main__":

    star = time.time()

    print("Connecting to DB")
    database_connection = psycopg.connect(
        "user=root password=root host=localhost port=5432 dbname=docprocai_service",
        autocommit=True,
        row_factory=psycopg.rows.dict_row
    )

    segment_database = SegmentDbConnector(database_connection)
    media_record_info_database = MediaRecordInfoDbConnector(database_connection)

    print("Loading segments and media records")

    segments = segment_database.get_all_entity_segments()
    media_records = media_record_info_database.get_all_media_records()

    topic_model = TopicModel(segments)

    print("Running Topic model")
    topic_model.create_topic_model()
    print("Topic model created")

    print("Adding tags")
    media_records_with_tags = topic_model.add_tags_to_media_records(segments, media_records)
    if media_records_with_tags is not None:
        for mrid, tags in media_records_with_tags.items():
            media_record_info_database.update_media_record_tags(mrid, list(tags))
    end = time.time()
    print("Done in " + str(end - star) + " seconds")
