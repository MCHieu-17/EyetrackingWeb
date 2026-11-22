# k6 summary

scenario: course_visits

- iterations: count=20.000, rate=4.782
- http_req_receiving: p(95)=0.281, p(99)=0.290, avg=0.139, min=0.030, med=0.134, max=0.292, p(90)=0.209
- http_req_failed: rate=0.000
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_waiting: med=8.214, max=10.460, p(90)=8.766, p(95)=9.231, p(99)=10.214, avg=7.796, min=5.442
- http_req_duration: p(95)=9.430, p(99)=10.404, avg=7.981, min=5.544, med=8.423, max=10.647, p(90)=8.983
- http_req_sending: max=0.061, p(90)=0.053, p(95)=0.054, p(99)=0.060, avg=0.047, min=0.035, med=0.046
- http_req_blocked: p(99)=0.096, avg=0.018, min=0.011, med=0.012, max=0.114, p(90)=0.016, p(95)=0.023
- http_req_connecting: p(95)=0.004, p(99)=0.067, avg=0.004, min=0.000, med=0.000, max=0.083, p(90)=0.000
- vus: min=1.000, max=1.000
- http_req_duration{expected_response:true}: p(99)=10.404, avg=7.981, min=5.544, med=8.423, max=10.647, p(90)=8.983, p(95)=9.430
