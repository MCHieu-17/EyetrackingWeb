# k6 summary

scenario: course_visits

- http_req_receiving: p(95)=0.473, p(99)=0.584, avg=0.261, min=0.073, med=0.243, max=0.611, p(90)=0.344
- vus: min=1.000, max=1.000
- http_req_tls_handshaking: avg=0.000, min=0.000, med=0.000, max=0.000, p(90)=0.000, p(95)=0.000, p(99)=0.000
- http_req_waiting: p(99)=76.861, avg=44.556, min=16.553, med=46.782, max=81.826, p(90)=51.579, p(95)=57.004
- http_req_duration{expected_response:true}: avg=44.861, min=16.817, med=47.110, max=81.953, p(90)=51.891, p(95)=57.188, p(99)=77.000
- http_req_sending: avg=0.044, min=0.015, med=0.043, max=0.078, p(90)=0.052, p(95)=0.056, p(99)=0.074
- http_req_failed: rate=0.000
- iterations: rate=4.066, count=20.000
- http_req_blocked: min=0.004, med=0.011, max=0.147, p(90)=0.016, p(95)=0.029, p(99)=0.123, avg=0.018
- http_req_connecting: avg=0.005, min=0.000, med=0.000, max=0.098, p(90)=0.000, p(95)=0.005, p(99)=0.079
- http_req_duration: p(95)=57.188, p(99)=77.000, avg=44.861, min=16.817, med=47.110, max=81.953, p(90)=51.891
