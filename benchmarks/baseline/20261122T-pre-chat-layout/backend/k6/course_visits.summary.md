# k6 summary

scenario: course_visits

- http_req_connecting: med=0.000, max=0.088, p(90)=0.000, p(95)=0.000, p(99)=0.087, avg=0.002, min=0.000
- http_req_duration{expected_response:true}: min=2.161, med=8.734, max=17.159, p(90)=13.288, p(95)=13.892, p(99)=15.948, avg=9.023
- http_req_sending: max=0.295, p(90)=0.056, p(95)=0.072, p(99)=0.263, avg=0.048, min=0.008, med=0.042
- iterations: rate=23.597, count=240.000
- http_req_blocked: min=0.002, med=0.011, max=0.554, p(90)=0.014, p(95)=0.016, p(99)=0.322, avg=0.019
- http_req_tls_handshaking: p(90)=0.000, p(95)=0.000, p(99)=0.000, avg=0.000, min=0.000, med=0.000, max=0.000
- http_req_duration: avg=9.023, min=2.161, med=8.734, max=17.159, p(90)=13.288, p(95)=13.892, p(99)=15.948
- http_req_failed: rate=0.000
- vus: min=5.000, max=5.000
- http_req_waiting: min=2.097, med=8.499, max=17.033, p(90)=13.032, p(95)=13.550, p(99)=15.634, avg=8.814
- http_req_receiving: p(99)=0.470, avg=0.161, min=0.016, med=0.128, max=0.856, p(90)=0.356, p(95)=0.405
