import typing

from .resources import Resources
from ..tags import Tags
from ..exceptions import *
from ..study import StudyInfo, Study
from ..helpers import to_dicom_date
from typing import List, Any, Union


class Studies(Resources):

    def __init__(self, api_client: 'OrthancApiClient'):
        super().__init__(api_client=api_client, url_segment='studies')

    def get(self, orthanc_id: str) -> Study:
        return Study(api_client=self._api_client, orthanc_id=orthanc_id)

    def get_instances_ids(self, orthanc_id: str) -> List[str]:
        instances_ids = []
        study_info = self._api_client.get_json(f"{self._url_segment}/{orthanc_id}")
        for series_id in study_info["Series"]:
            instances_ids.extend(self._api_client.series.get_instances_ids(series_id))

        return instances_ids

    def get_series_ids(self, orthanc_id: str) -> List[str]:
        study_info = self._api_client.get_json(f"{self._url_segment}/{orthanc_id}")
        return study_info["Series"]

    def get_first_instance_id(self, orthanc_id: str) -> str:
        return self.get_instances_ids(orthanc_id=orthanc_id)[0]

    def get_parent_patient_id(self, orthanc_id: str) -> str:
        study_info = self._api_client.get_json(f"{self._url_segment}/{orthanc_id}")
        return study_info['ParentPatient']

    def lookup(self, dicom_id: str) -> str:
        """
        finds a study in Orthanc based on its StudyInstanceUid

        Returns
        -------
        the instance id of the study or None if not found
        """
        return self._lookup(filter='Study', dicom_id=dicom_id)

    def find(self, query: object, case_sensitive: bool = True) -> typing.List[Study]:
        payload = {
            "Level": "Study",
            "Query": query,
            "Expand": True,
            "CaseSensitive": case_sensitive
        }

        r = self._api_client.post(
            endpoint=f"tools/find",
            json=payload)

        studies = []
        for json_study in r.json():
            studies.append(Study.from_json(self._api_client, json_study))

        return studies

    def anonymize(self, orthanc_id: str, replace_tags={}, keep_tags=[], delete_original=True, force=False) -> str:
        return self._anonymize(
            orthanc_id=orthanc_id,
            replace_tags=replace_tags,
            keep_tags=keep_tags,
            delete_original=delete_original,
            force=force
        )

    def modify(self, orthanc_id: str, replace_tags={}, remove_tags=[], delete_original=True, force=False) -> str:
        return self._modify(
            orthanc_id=orthanc_id,
            replace_tags=replace_tags,
            remove_tags=remove_tags,
            delete_original=delete_original,
            force=force
        )

    def modify_instance_by_instance(self, orthanc_id: str, replace_tags: Any = {}, remove_tags: List[str] = [], delete_original: bool = True, force: bool = True) -> str:
        modified_instances_ids = self._api_client.instances.modify_bulk(
            orthanc_ids=self.get_instances_ids(orthanc_id),
            replace_tags=replace_tags,
            remove_tags=remove_tags,
            delete_original=delete_original,
            force=force
        )

        return self._api_client.instances.get_parent_study_id(modified_instances_ids[0])

    def get_tags(self, orthanc_id: str) -> Tags:
        """
        returns tags from a "random" instance in which you should safely get the study/patient tags
        """
        return self._api_client.instances.get_tags(self.get_first_instance_id(orthanc_id=orthanc_id))

    def merge(self, target_study_id: str, source_series_id: Union[List[str], str], keep_source: bool):

        if isinstance(source_series_id, str):
            source_series_id = [source_series_id]

        return self._api_client.post(
            endpoint=f"{self._url_segment}/{target_study_id}/merge",
            json={
                "Resources": source_series_id,
                "KeepSource": keep_source
            }
        )

    def attach_pdf(self, study_id, pdf_path, series_description, datetime = None):
        """
        Creates a new instance with the PDF embedded.  This instance is a part of a new series attached to an existing study

        Returns:
            the instance_orthanc_id of the created instance
        """
        series_tags = {}
        series_tags["SeriesDescription"] = series_description
        if datetime is not None:
            series_tags["SeriesDate"] = to_dicom_date(datetime)
            series_tags["SeriesTime"] = to_dicom_date(datetime)

        return self._api_client.create_pdf(pdf_path, series_tags, parent_id = study_id)

    def get_pdf_instances(self, study_id, max_instance_count_in_series_to_analyze = 2):
        """
        Returns the instanceIds of the instances containing PDF
        Args:
            study_id: The id of the study to search in
            max_instance_count_in_series_to_analyze: skip series containing too many instances (they are very unlikely to contain pdf reports).  set it to 0 to disable the check.

        Returns: an array of instance orthancId
        """

        pdf_ids = []
        series_list = self.get_series_ids(study_id)

        for series_id in series_list:
            instances_ids = self._api_client.series.get_instances_ids(series_id)
            if max_instance_count_in_series_to_analyze > 0 and len(instances_ids) <= max_instance_count_in_series_to_analyze:
                for instance_id in instances_ids:
                    if self._api_client.instances.is_pdf(instance_id):
                        pdf_ids.append(instance_id)

        return pdf_ids

    def download_study(self, study_id, path):
        """
        downloads all instances from the study to disk
        Args:
            study_id: the studyid to download
            path: the directory path where to store the downloaded files

        Returns:
            an array of DownloadedInstance
        """
        downloaded_instances = []
        for series_id in self.get_series_ids(study_id):
            downloaded_instances.extend(self._api_client.series.download_series(series_id, path))

        return downloaded_instances