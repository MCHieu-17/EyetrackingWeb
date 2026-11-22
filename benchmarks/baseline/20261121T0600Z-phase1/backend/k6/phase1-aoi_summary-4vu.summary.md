# k6 summary

scenario: aoi_summary

- http_req_duration{expected_response:true}: avg=246.520, min=191.259, med=235.599, max=354.176, p(90)=295.530, p(95)=308.572, p(99)=341.403
- http_req_blocked: med=0.010, max=0.116, p(90)=0.013, p(95)=0.015, p(99)=0.115, avg=0.011, min=0.002
- http_req_sending: med=0.047, max=0.170, p(90)=0.070, p(95)=0.077, p(99)=0.123, avg=0.043, min=0.004
- http_req_receiving: p(95)=0.520, p(99)=0.922, avg=0.276, min=0.089, med=0.244, max=1.487, p(90)=0.436
- http_req_tls_handshaking: max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000
- http_req_duration: min=191.259, med=235.599, max=354.176, p(90)=295.530, p(95)=308.572, p(99)=341.403, avg=246.520
- iterations: count=272.000, rate=8.936
- http_req_connecting: med=0.000, max=0.082, p(90)=0.000, p(95)=0.000, p(99)=0.077, avg=0.001, min=0.000
- vus: min=4.000, max=4.000
- http_req_failed: rate=0.000
- http_req_waiting: max=353.981, p(90)=294.595, p(95)=308.289, p(99)=341.135, avg=246.201, min=191.032, med=235.292
